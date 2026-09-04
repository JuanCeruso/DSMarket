# -*- coding: utf-8 -*-
"""
Orquestador: un comando que ejecuta todo y deja constancia de lo que hizo.

Hasta aquí el proyecto se ejecutaba abriendo cuadernos en un orden que había que recordar. Eso
no es un sistema: es un procedimiento que vive en la cabeza de quien lo montó. Un sistema se
reconoce en que se puede lanzar entero con un comando, sabe en qué etapa está, se detiene cuando
algo falla y deja escrito qué pasó.

    python3 operacion/orquestador.py                    # todo, de principio a fin
    python3 operacion/orquestador.py --desde predecir   # reanudar desde una etapa
    python3 operacion/orquestador.py --solo contratos   # una sola etapa
    python3 operacion/orquestador.py --estado           # qué pasó en las últimas ejecuciones
    python3 operacion/orquestador.py --simular          # enseña el plan sin ejecutarlo

Las etapas se detienen ante el primer fallo **bloqueante**. Los contratos de datos corren dos
veces a propósito: después de construir el almacén y antes de publicar las predicciones. La
segunda pasada es la que impide que un modelo roto llegue a la API.
"""
from __future__ import annotations
import argparse, os, subprocess, sys, time
import pandas as pd
from base import RAIZ, anexar, leer, ahora, nuevo_id

PY = sys.executable


def _pipeline(capa):
    return [PY, os.path.join(RAIZ, "lakehouse", "scripts", "pipeline.py"), capa]


# nombre, descripción, comando o función, ¿su fallo detiene el pipeline?
ETAPAS = [
    ("bronce",     "Ingesta de los CSV a Parquet sin transformar",      _pipeline("bronze"), True),
    ("plata",      "Limpieza, formato largo y reglas de calidad",       _pipeline("silver"), True),
    ("oro",        "Modelo dimensional y agregados de consumo",         _pipeline("gold"),   True),
    ("contratos",  "Contratos de datos sobre el almacén construido",    "contratos",         True),
    ("entrenar",   "Entrenamiento de los modelos media y p90",          "entrenar",          True),
    ("predecir",   "Predicción a 28 días y carga en fact_predicciones", "predecir",          True),
    ("reposicion", "Cálculo de niveles objetivo por serie",             "reposicion",        True),
    ("contratos2", "Contratos otra vez, antes de publicar",             "contratos",         True),
    ("monitor",    "Métricas, deriva y umbrales de alerta",             "monitor",          False),
]


def _ejecutar_comando(cmd) -> tuple[bool, str]:
    r = subprocess.run(cmd, capture_output=True, text=True)
    salida = (r.stdout or "") + (r.stderr or "")
    return r.returncode == 0, salida[-2000:]


def _ejecutar_interno(nombre, ejecucion_id) -> tuple[bool, str]:
    if nombre == "contratos":
        from contratos import verificar
        ok, _ = verificar(detalle=False, ejecucion_id=ejecucion_id)
        return ok, ""
    if nombre == "monitor":
        from monitor import main as monitorizar
        return monitorizar(1.20, 0.15, 0.20), ""
    if nombre in ("entrenar", "predecir", "reposicion"):
        guion = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"{nombre}.py")
        if not os.path.exists(guion):
            return False, (f"Falta {nombre}.py. Esta etapa todavía se ejecuta desde el cuaderno "
                           f"correspondiente; ver el README de esta carpeta.")
        return _ejecutar_comando([PY, guion])
    return False, f"etapa desconocida: {nombre}"


def correr(desde=None, solo=None, simular=False):
    ejecucion_id = nuevo_id("run")
    etapas = ETAPAS
    if solo:
        etapas = [e for e in ETAPAS if e[0] == solo]
        if not etapas:
            print(f"No existe la etapa «{solo}». Etapas: "
                  + ", ".join(e[0] for e in ETAPAS)); return False
    elif desde:
        nombres = [e[0] for e in ETAPAS]
        if desde not in nombres:
            print(f"No existe la etapa «{desde}». Etapas: " + ", ".join(nombres)); return False
        etapas = ETAPAS[nombres.index(desde):]

    print(f"\nEJECUCIÓN {ejecucion_id}   ·   {len(etapas)} etapas")
    print("=" * 72)
    if simular:
        for i, (n, d, _, bloq) in enumerate(etapas, 1):
            print(f"  {i}. {n:<11} {d}" + ("" if bloq else "   (no bloqueante)"))
        print("\n(simulación: no se ejecutó nada)")
        return True

    t_total = time.time()
    registros, todo_ok = [], True
    for i, (nombre, descripcion, accion, bloqueante) in enumerate(etapas, 1):
        print(f"\n[{i}/{len(etapas)}] {nombre} — {descripcion}", flush=True)
        t0 = time.time()
        try:
            if isinstance(accion, list):
                ok, salida = _ejecutar_comando(accion)
            else:
                ok, salida = _ejecutar_interno(accion, ejecucion_id)
        except Exception as e:
            ok, salida = False, f"{type(e).__name__}: {e}"
        dur = time.time() - t0
        estado = "OK" if ok else ("FALLO" if bloqueante else "AVISO")
        print(f"      {estado} en {dur:.1f}s")
        if not ok and salida.strip():
            print("      " + salida.strip().replace("\n", "\n      ")[:900])
        registros.append({"ejecucion_id": ejecucion_id, "etapa": nombre, "estado": estado,
                          "inicio": ahora(), "segundos": round(dur, 1),
                          "mensaje": salida.strip()[-500:]})
        if not ok and bloqueante:
            todo_ok = False
            print(f"\n  Etapa bloqueante fallida: se detiene aquí y no se publica nada.")
            print(f"  Para reanudar cuando esté resuelto:")
            print(f"      python3 operacion/orquestador.py --desde {nombre}")
            break

    anexar("fact_ejecuciones", registros)
    print("\n" + "=" * 72)
    print(f"{'COMPLETADA' if todo_ok else 'DETENIDA'} · {time.time()-t_total:.0f}s · {ejecucion_id}")
    return todo_ok


def estado(n=5):
    df = leer("fact_ejecuciones")
    if df.empty:
        print("No hay ejecuciones registradas."); return
    ult = df["ejecucion_id"].drop_duplicates().tail(n)
    for eid in ult:
        g = df[df["ejecucion_id"] == eid]
        malas = (g["estado"] == "FALLO").sum()
        print(f"\n{eid}   {g['inicio'].iloc[0]}   "
              f"{'OK' if malas == 0 else 'FALLO'}   {g['segundos'].sum():.0f}s")
        for _, r in g.iterrows():
            print(f"   {r['estado']:<6} {r['etapa']:<11} {r['segundos']:>7.1f}s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", help="reanudar desde esta etapa")
    ap.add_argument("--solo", help="ejecutar solo esta etapa")
    ap.add_argument("--simular", action="store_true", help="mostrar el plan sin ejecutarlo")
    ap.add_argument("--estado", action="store_true", help="ver las últimas ejecuciones")
    a = ap.parse_args()
    if a.estado:
        estado()
    else:
        sys.exit(0 if correr(a.desde, a.solo, a.simular) else 1)
