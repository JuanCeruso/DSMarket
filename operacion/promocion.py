# -*- coding: utf-8 -*-
"""
Puerta de promoción: el modelo nuevo tiene que ganarse el puesto.

El fallo silencioso más caro de un sistema de predicción no es que el modelo falle: es que un
modelo peor sustituya al que funcionaba, sin que nadie lo decida. Pasa solo, cada vez que
«entrenar» y «desplegar» son el mismo paso. Aquí no lo son: `entrenar.py` deja un **candidato**
y esta puerta decide si pasa.

Las reglas, y por qué cada una:

  1. **Cordura absoluta.** La cobertura del p90 tiene que estar entre el 85% y el 95%. Un
     intervalo que cubre el 99% no es prudente, es inútil: infla el stock de seguridad de todo
     el surtido. Uno que cubre el 70% deja sin colchón justo donde hace falta.
  2. **No empeorar.** El MAE del candidato no puede superar al del vigente en más de un 5%. El
     margen no es cero a propósito: el ruido de validación entre dos ventanas de cuatro semanas
     es de ese orden, y una puerta que rechaza ruido bloquea el sistema para siempre.
  3. **Reproducible.** Si el árbol de trabajo está sucio, el modelo no se puede reconstruir a
     partir de su SHA. Se avisa, y con `--exigir-limpio` se rechaza.
  4. **Contratos en verde.** Un modelo entrenado sobre datos que no pasan los contratos no se
     promueve aunque sus métricas sean excelentes; probablemente lo sean *por eso*.

Si el candidato no pasa, **no se para el sistema**: sigue mandando el vigente y el pipeline
continúa prediciendo con él. Esa es la razón de ser de la puerta. Solo es un fallo bloqueante
cuando no hay vigente al que volver, es decir, en el primer entrenamiento.

    python3 operacion/promocion.py
    python3 operacion/promocion.py --margen 0.02 --exigir-limpio
    python3 operacion/promocion.py --forzar          # promover a mano, dejando dicho que fue a mano
"""
from __future__ import annotations
import argparse, sys
import modelos as reg

MARGEN_MAE = 0.05          # cuánto se tolera empeorar frente al vigente
COBERTURA_MIN = 0.85
COBERTURA_MAX = 0.95


def _num(d: dict | None, clave: str):
    if not d:
        return None
    v = d.get(clave)
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def evaluar(cand: dict, vig: dict | None, margen: float, exigir_limpio: bool) -> tuple[bool, list, list]:
    """Aplica las reglas y devuelve (pasa, motivos_de_rechazo, avisos)."""
    fallos, avisos = [], []

    # ---------- 1. cordura absoluta ----------
    cob = _num(cand, "metrica_cobertura_p90")
    if cob is None:
        avisos.append("el candidato no trae cobertura del p90: no se puede comprobar la cordura")
    elif not (COBERTURA_MIN <= cob <= COBERTURA_MAX):
        fallos.append(f"cobertura del p90 en {cob:.1%}, fuera de la banda "
                      f"[{COBERTURA_MIN:.0%}, {COBERTURA_MAX:.0%}]")

    mae_c = _num(cand, "metrica_mae_validacion")
    if mae_c is None:
        fallos.append("el candidato no trae MAE de validación: no hay nada que comparar")
    elif not (mae_c > 0):
        fallos.append(f"MAE de validación imposible ({mae_c})")

    # ---------- 2. no empeorar ----------
    mae_v = _num(vig, "metrica_mae_validacion")
    if vig is None:
        avisos.append("no hay modelo vigente: este es el primero, se promueve si pasa la cordura")
    elif mae_c is None or mae_v is None:
        avisos.append("falta el MAE de alguno de los dos: se compara solo por cordura")
    else:
        deterioro = (mae_c - mae_v) / mae_v
        if deterioro > margen:
            fallos.append(f"MAE {mae_c:.4f} frente a {mae_v:.4f} del vigente: "
                          f"{deterioro:+.1%}, por encima del margen del {margen:.0%}")

    # ---------- 3. reproducible ----------
    sha = str(cand.get("sha_git") or "")
    if "sucio" in sha or sha == "sin_git":
        texto = ("el modelo se entrenó con cambios sin comitear: no se puede reconstruir"
                 if "sucio" in sha else "no hay repositorio git: la procedencia del código se pierde")
        (fallos if exigir_limpio else avisos).append(texto)

    # ---------- 4. contratos ----------
    try:
        from contratos import verificar
        ok, _ = verificar(detalle=False)
        if not ok:
            fallos.append("los contratos de datos no están en verde")
    except Exception as e:
        avisos.append(f"no se pudieron ejecutar los contratos aquí ({type(e).__name__}); "
                      f"el orquestador ya los ejecuta como etapa propia")

    return not fallos, fallos, avisos


def main(margen, exigir_limpio, forzar, tipo):
    print("\nPUERTA DE PROMOCIÓN\n" + "-" * 68)
    cand = reg.candidato(tipo)
    vig = reg.vigente(tipo)

    if cand is None:
        print("No hay ningún candidato pendiente.")
        if vig:
            print(f"Sigue vigente {vig['modelo_id']}. Nada que hacer.")
            return True
        print("Y tampoco hay modelo vigente. Ejecutá antes: python3 operacion/entrenar.py")
        return False

    print(f"  candidato : {cand['modelo_id']}  ({cand.get('sha_git', '?')})")
    print(f"  vigente   : {vig['modelo_id'] if vig else '— ninguno —'}")
    print()
    for clave, etiqueta, formato in [("metrica_mae_validacion", "MAE de validación", "{:.4f}"),
                                     ("metrica_cobertura_p90", "cobertura del p90", "{:.1%}")]:
        c, v = _num(cand, clave), _num(vig, clave)
        linea = f"  {etiqueta:<20} " + (formato.format(c) if c is not None else "—")
        if v is not None and c is not None:
            linea += f"   (vigente {formato.format(v)}  ·  {(c - v) / v:+.1%})"
        print(linea)

    pasa, fallos, avisos = evaluar(cand, vig, margen, exigir_limpio)
    print()
    for a in avisos:
        print(f"  aviso   · {a}")
    for f in fallos:
        print(f"  RECHAZO · {f}")

    print("\n" + "-" * 68)
    if forzar and not pasa:
        motivo = "promoción forzada a mano pese a: " + "; ".join(fallos)
        reg.promover(cand["modelo_id"], motivo)
        print("PROMOVIDO A MANO pese a los rechazos. Queda anotado en el registro como forzado.")
        return True
    if pasa:
        motivo = ("primer modelo del registro" if vig is None
                  else f"supera la puerta frente a {vig['modelo_id']}")
        reg.promover(cand["modelo_id"], motivo)
        print(f"PROMOVIDO · {cand['modelo_id']} pasa a vigente.")
        if vig:
            print(f"           {vig['modelo_id']} queda retirado; sus pesos siguen en disco.")
            print("           Para deshacer: python3 operacion/modelos.py --retroceder")
        return True

    reg.rechazar(cand["modelo_id"], "; ".join(fallos))
    print(f"RECHAZADO · {cand['modelo_id']} no pasa la puerta.")
    if vig:
        print(f"           Sigue mandando {vig['modelo_id']}: el sistema no se para y")
        print("           las predicciones de hoy se hacen con el modelo de siempre.")
        return True
    print("           Y no hay vigente al que volver: el pipeline se detiene aquí.")
    return False


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--margen", type=float, default=MARGEN_MAE,
                    help="deterioro relativo de MAE tolerado frente al vigente")
    ap.add_argument("--exigir-limpio", action="store_true",
                    help="rechazar si el árbol de trabajo tiene cambios sin comitear")
    ap.add_argument("--forzar", action="store_true",
                    help="promover aunque no pase, dejándolo anotado")
    ap.add_argument("--tipo", default="lightgbm_bloques")
    a = ap.parse_args()
    sys.exit(0 if main(a.margen, a.exigir_limpio, a.forzar, a.tipo) else 1)
