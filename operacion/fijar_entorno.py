# -*- coding: utf-8 -*-
"""
Fijar el entorno: que «reproducilo» sea una instrucción y no un deseo.

`requirements.txt` dice *qué* hace falta. No dice *cuál*: `pandas` a secas significa «la versión
de pandas que hubiera el día que lo instalaste». Dos personas siguiendo el mismo README pueden
acabar con entornos distintos, y dos entrenamientos con el mismo código pueden dar números
distintos sin que nadie sepa por qué.

Este guion hace dos cosas:

    python3 operacion/fijar_entorno.py              # escribe requirements-bloqueado.txt
    python3 operacion/fijar_entorno.py --comprobar  # ¿el entorno de ahora es el fijado?

La comprobación es la parte que se usa a diario. El registro de modelos guarda la huella del
entorno con el que se entrenó cada modelo; si la de hoy no coincide con la del modelo vigente,
conviene saberlo **antes** de comparar métricas y concluir que el modelo empeoró.
"""
from __future__ import annotations
import argparse, os, subprocess, sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLOQUEADO = os.path.join(RAIZ, "requirements-bloqueado.txt")

CABECERA = """\
# =============================================================================
#  Entorno fijado de DSMarket — generado, no editado a mano
#
#  Se regenera con:   python3 operacion/fijar_entorno.py
#  Se comprueba con:  python3 operacion/fijar_entorno.py --comprobar
#
#  Este fichero es el que reproduce los resultados de la memoria. `requirements.txt`
#  es para instalar el proyecto; este es para reproducirlo. Son cosas distintas y por
#  eso son dos ficheros.
#
#  Generado con {interprete} el {fecha}
# =============================================================================
"""

# Los paquetes que deciden el resultado numérico. El resto del entorno puede variar sin
# consecuencias; estos no.
CRITICOS = ["lightgbm", "xgboost", "numpy", "pandas", "scipy", "scikit-learn",
            "statsmodels", "duckdb", "pyarrow", "prophet"]


def _congelado() -> list[str]:
    r = subprocess.run([sys.executable, "-m", "pip", "freeze", "--exclude-editable"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"pip freeze falló:\n{r.stderr}")
    return [l.strip() for l in r.stdout.splitlines() if l.strip() and not l.startswith("#")]


def _instalados(lineas: list[str]) -> dict[str, str]:
    d = {}
    for l in lineas:
        if "==" in l:
            nombre, version = l.split("==", 1)
            d[nombre.strip().lower().replace("_", "-")] = version.strip()
    return d


def escribir() -> None:
    import datetime as dt
    lineas = _congelado()
    inst = _instalados(lineas)
    faltan = [p for p in CRITICOS if p not in inst]

    with open(BLOQUEADO, "w") as f:
        f.write(CABECERA.format(
            interprete=f"Python {sys.version.split()[0]}",
            fecha=dt.date.today().isoformat()))
        f.write(f"# Python {sys.version.split()[0]}\n\n")
        f.write("# --- paquetes que deciden el resultado numérico ---\n")
        for p in CRITICOS:
            if p in inst:
                f.write(f"{p}=={inst[p]}\n")
        f.write("\n# --- el resto del entorno, por completitud ---\n")
        for l in sorted(lineas, key=str.lower):
            nombre = l.split("==")[0].strip().lower().replace("_", "-")
            if nombre not in CRITICOS:
                f.write(l + "\n")

    print(f"Escrito {os.path.relpath(BLOQUEADO, RAIZ)} con {len(lineas)} paquetes.")
    print(f"Python {sys.version.split()[0]}")
    for p in CRITICOS:
        if p in inst:
            print(f"  {p:<14} {inst[p]}")
    if faltan:
        print("\nNo están instalados (y por tanto no quedan fijados): " + ", ".join(faltan))
        print("Si el proyecto los usa, instalalos antes de volver a generar el fichero.")
    print("\nComiteá este fichero. Es el que reproduce los números de la memoria.")


def comprobar() -> bool:
    if not os.path.exists(BLOQUEADO):
        print("No hay entorno fijado todavía. Generalo con:")
        print("    python3 operacion/fijar_entorno.py")
        return False
    esperado = _instalados([l for l in open(BLOQUEADO).read().splitlines()
                            if l.strip() and not l.startswith("#")])
    actual = _instalados(_congelado())

    diferencias, ausentes = [], []
    for nombre, version in esperado.items():
        if nombre not in actual:
            ausentes.append(f"{nombre}=={version}")
        elif actual[nombre] != version:
            diferencias.append((nombre, version, actual[nombre]))

    criticas = [d for d in diferencias if d[0] in CRITICOS]
    print("\nCOMPROBACIÓN DEL ENTORNO\n" + "-" * 68)
    print(f"  intérprete : Python {sys.version.split()[0]}")
    print(f"  fijados    : {len(esperado)} paquetes")
    print(f"  distintos  : {len(diferencias)}  ({len(criticas)} de los que deciden el resultado)")
    print(f"  ausentes   : {len(ausentes)}")

    if criticas:
        print("\n  Diferencias que pueden cambiar los números:")
        for nombre, esp, act in criticas:
            print(f"    {nombre:<14} fijado {esp:<12} instalado {act}")
        print("\n  Si vas a comparar métricas con las de la memoria, alineá primero el entorno:")
        print("      pip install -r requirements-bloqueado.txt")
    elif diferencias:
        print("\n  Hay diferencias, pero ninguna en los paquetes que deciden el resultado.")
    else:
        print("\n  El entorno coincide con el fijado.")
    return not criticas


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--comprobar", action="store_true",
                    help="comparar el entorno de ahora con el fijado, sin reescribirlo")
    a = ap.parse_args()
    if a.comprobar:
        sys.exit(0 if comprobar() else 1)
    escribir()
