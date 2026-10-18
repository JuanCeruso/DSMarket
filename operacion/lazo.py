# -*- coding: utf-8 -*-
"""
Lazo cerrado: que la monitorización sirva para algo.

Hasta aquí el monitor escribía una alerta y la alerta se quedaba ahí, esperando que alguien la
leyera. Eso es un tablero, no un lazo. Un lazo cerrado es cuando la señal vuelve a entrar en el
sistema y cambia lo que el sistema hace.

La política está escrita aquí, en un sitio, y es deliberadamente conservadora:

  **Se reentrena si** hay dos ejecuciones seguidas en alerta —una sola puede ser un festivo mal
  codificado— **o** si han pasado más de 28 días desde la última promoción, que es el horizonte
  de predicción y por tanto el ciclo natural de refresco.

  **No se reentrena si** los contratos de datos no están en verde. Es la regla que más veces
  salva el sistema: si la alerta viene de que los datos cambiaron de forma, reentrenar produce
  un modelo nuevo que aprende el error y unas métricas de validación estupendas calculadas sobre
  los mismos datos rotos. El diagnóstico va antes que el remedio.

  **Tampoco se reentrena** si ya se reentrenó hace menos de 7 días. Sin esta regla, un lazo con
  una alerta persistente entra en bucle: reentrena, sigue en alerta, reentrena. El límite
  convierte el bucle en una escalera que alguien puede ver subir.

Reentrenar no es promover: lo que sale del reentrenamiento es un candidato, y sigue teniendo que
pasar por `promocion.py`. El lazo automatiza el trabajo, no la decisión.

    python3 operacion/lazo.py                # diagnóstico: qué haría y por qué
    python3 operacion/lazo.py --ejecutar     # además lo hace
"""
from __future__ import annotations
import argparse, datetime as dt, os, subprocess, sys
import pandas as pd
from base import leer, anexar, ahora, nuevo_id
import modelos as reg

ALERTAS_SEGUIDAS = 2       # ejecuciones consecutivas en alerta que disparan el reentrenamiento
DIAS_REFRESCO = 28         # antigüedad máxima del modelo vigente
DIAS_ENFRIAMIENTO = 7      # mínimo entre dos reentrenamientos
AQUI = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def _fecha(valor) -> dt.datetime | None:
    try:
        return pd.to_datetime(valor).to_pydatetime()
    except (ValueError, TypeError):
        return None


def _dias_desde(valor) -> float | None:
    f = _fecha(valor)
    return None if f is None else (dt.datetime.now() - f).total_seconds() / 86400


def diagnosticar(tipo: str = "lightgbm_bloques") -> dict:
    """Mira el estado del sistema y devuelve la decisión con sus razones."""
    met = leer("fact_metricas")
    vig = reg.vigente(tipo)
    hist = reg.historial(tipo)

    # ---------- señales ----------
    ultimas = met.tail(ALERTAS_SEGUIDAS)["estado"].tolist() if not met.empty else []
    en_alerta = len(ultimas) == ALERTAS_SEGUIDAS and all(e == "ALERTA" for e in ultimas)

    edad = _dias_desde(vig.get("momento_promocion") or vig.get("momento_entrenamiento")) if vig else None
    caducado = edad is not None and edad > DIAS_REFRESCO

    if hist.empty:
        desde_ultimo = None
    else:
        desde_ultimo = _dias_desde(hist["momento_entrenamiento"].max())
    enfriando = desde_ultimo is not None and desde_ultimo < DIAS_ENFRIAMIENTO

    contratos_ok, detalle_contratos = _contratos()

    # ---------- decisión ----------
    razones_a_favor, razones_en_contra = [], []
    if en_alerta:
        razones_a_favor.append(f"{ALERTAS_SEGUIDAS} ejecuciones seguidas del monitor en alerta")
    if caducado:
        razones_a_favor.append(f"el modelo vigente tiene {edad:.0f} días "
                               f"(el horizonte de predicción es {DIAS_REFRESCO})")
    if vig is None:
        razones_a_favor.append("no hay modelo vigente")

    if not contratos_ok:
        razones_en_contra.append(f"los contratos de datos no están en verde ({detalle_contratos})")
    if enfriando:
        razones_en_contra.append(f"el último entrenamiento fue hace {desde_ultimo:.1f} días "
                                 f"(mínimo {DIAS_ENFRIAMIENTO})")

    reentrenar = bool(razones_a_favor) and not razones_en_contra
    return {
        "reentrenar": reentrenar,
        "a_favor": razones_a_favor,
        "en_contra": razones_en_contra,
        "estado_monitor": ultimas[-1] if ultimas else "sin datos",
        "edad_modelo_dias": edad,
        "contratos_ok": contratos_ok,
    }


def _contratos() -> tuple[bool, str]:
    try:
        from contratos import verificar
        ok, res = verificar(detalle=False)
        n = len(res) if hasattr(res, "__len__") else 0
        return ok, "todos en verde" if ok else f"{n} comprobaciones ejecutadas, alguna en rojo"
    except Exception as e:
        return True, f"no se pudieron ejecutar aquí ({type(e).__name__}); se asume el veredicto del orquestador"


def _correr(guion: str, *args) -> bool:
    ruta = os.path.join(AQUI, guion)
    print(f"\n  ── {guion} " + " ".join(args) + "\n", flush=True)
    return subprocess.run([PY, ruta, *args]).returncode == 0


def main(ejecutar: bool, tipo: str):
    d = diagnosticar(tipo)
    print("\nLAZO CERRADO · ¿hay que reentrenar?\n" + "-" * 68)
    print(f"  último veredicto del monitor : {d['estado_monitor']}")
    print(f"  edad del modelo vigente      : "
          + (f"{d['edad_modelo_dias']:.0f} días" if d["edad_modelo_dias"] is not None else "—"))
    print(f"  contratos de datos           : {'en verde' if d['contratos_ok'] else 'EN ROJO'}")
    print()
    for r in d["a_favor"]:
        print(f"  a favor    · {r}")
    for r in d["en_contra"]:
        print(f"  EN CONTRA  · {r}")
    if not d["a_favor"] and not d["en_contra"]:
        print("  nada que reportar: el sistema está dentro de sus umbrales.")

    print("\n" + "-" * 68)
    decision_id = nuevo_id("lazo")
    anexar("fact_lazo", [{
        "decision_id": decision_id, "momento": ahora(), "reentrenar": d["reentrenar"],
        "ejecutado": bool(ejecutar and d["reentrenar"]),
        "a_favor": " | ".join(d["a_favor"]), "en_contra": " | ".join(d["en_contra"]),
        "estado_monitor": d["estado_monitor"],
    }])

    if not d["reentrenar"]:
        if d["en_contra"] and d["a_favor"]:
            print("DECISIÓN: no reentrenar todavía. Hay motivo, pero también un impedimento,")
            print("y reentrenar sobre datos rotos produce un modelo roto con métricas nuevas.")
        else:
            print("DECISIÓN: no hace falta reentrenar.")
        return True

    if not ejecutar:
        print("DECISIÓN: corresponde reentrenar. Para hacerlo:")
        print("    python3 operacion/lazo.py --ejecutar")
        return True

    print("DECISIÓN: reentrenar. El resultado será un candidato, no un modelo desplegado.")
    for guion in ("entrenar.py", "promocion.py"):
        if not _correr(guion):
            print(f"\n  {guion} falló. El lazo se detiene y el modelo vigente sigue intacto.")
            return False
    print("\n  El candidato pasó por la puerta. Para que las predicciones lo usen:")
    print("      python3 operacion/orquestador.py --desde predecir")
    return True


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ejecutar", action="store_true", help="además de diagnosticar, actuar")
    ap.add_argument("--tipo", default="lightgbm_bloques")
    a = ap.parse_args()
    sys.exit(0 if main(a.ejecutar, a.tipo) else 1)
