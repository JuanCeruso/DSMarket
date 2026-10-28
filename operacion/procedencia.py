# -*- coding: utf-8 -*-
"""
Procedencia: de dónde salió exactamente este modelo.

Un identificador de modelo dice *cuál* es. La procedencia dice *de qué* se hizo. Son tres cosas
distintas y hacen falta las tres para que «reproducilo» sea una instrucción y no un deseo:

  1. **El código.** El SHA del commit y si el árbol de trabajo estaba limpio. Un modelo entrenado
     con cambios sin comitear no es reproducible y conviene que quede dicho, no escondido.
  2. **Los datos.** Una huella del almacén en el momento del entrenamiento. No sirve la fecha:
     dos ejecuciones del mismo día pueden ver almacenes distintos si alguien reconstruyó la capa
     de plata en medio. La huella se calcula sobre lo que el modelo realmente lee.
  3. **El entorno.** Versión de Python y de las bibliotecas que deciden el resultado numérico.
     LightGBM cambia de resultado entre versiones menores; no anotarlo es perder la mitad del
     experimento.

Las tres caben en tres cadenas de texto y se guardan como columnas de `dim_modelo`. No hace
falta más: con el SHA se recupera el código, con la huella se comprueba si el almacén es el
mismo, y con el entorno se sabe si la diferencia viene de ahí.

    python3 operacion/procedencia.py        # muestra la procedencia de ahora mismo
"""
from __future__ import annotations
import hashlib, os, subprocess, sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLD = os.path.join(RAIZ, "lakehouse", "gold")

# Las tablas que el entrenamiento lee de verdad. Cambiar esta lista cambia el significado de la
# huella, así que se declara aquí y no se deduce del directorio: si mañana se añade una tabla al
# almacén que el modelo no usa, la huella no debe moverse por eso.
TABLAS_DE_ENTRADA = ["fact_ventas", "dim_serie", "dim_calendario", "dim_producto", "dim_tienda"]


def _git(*args: str) -> str:
    try:
        r = subprocess.run(["git", "-C", RAIZ, *args], capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def sha_git() -> str:
    """SHA corto del commit, con sufijo «+sucio» si hay cambios sin comitear.

    El sufijo importa: un modelo entrenado sobre un árbol sucio no se puede reconstruir a partir
    del SHA, y es mejor saberlo al leer el registro que descubrirlo intentando reproducirlo.
    """
    sha = _git("rev-parse", "--short=12", "HEAD")
    if not sha:
        return "sin_git"
    sucio = bool(_git("status", "--porcelain"))
    return f"{sha}+sucio" if sucio else sha


def rama_git() -> str:
    return _git("rev-parse", "--abbrev-ref", "HEAD") or "sin_git"


def huella_datos(tablas: list[str] | None = None) -> str:
    """Huella de 16 caracteres del almacén que ve el entrenamiento.

    Se calcula sobre (nombre, tamaño en bytes, fecha de modificación) de cada fichero de entrada.
    No es un hash del contenido —leer 163 MB en cada ejecución sería caro y no aporta: los
    ficheros los escribe el pipeline entero, nunca se editan en el sitio—, pero sí detecta
    cualquier reconstrucción del almacén, que es exactamente lo que tiene que detectar.
    """
    tablas = tablas or TABLAS_DE_ENTRADA
    h = hashlib.sha256()
    for t in sorted(tablas):
        ruta = os.path.join(GOLD, f"{t}.parquet")
        if not os.path.exists(ruta):
            h.update(f"{t}:ausente".encode())
            continue
        st = os.stat(ruta)
        h.update(f"{t}:{st.st_size}:{int(st.st_mtime)}".encode())
    return h.hexdigest()[:16]


def huella_entorno() -> str:
    """Versiones de lo que decide el resultado numérico, en una línea legible."""
    partes = [f"python{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"]
    for nombre in ("lightgbm", "numpy", "pandas", "duckdb", "scipy"):
        try:
            mod = __import__(nombre)
            partes.append(f"{nombre}{getattr(mod, '__version__', '?')}")
        except ImportError:
            partes.append(f"{nombre}ausente")
    return " ".join(partes)


def completa() -> dict:
    """Las tres huellas juntas, tal como se guardan en `dim_modelo`."""
    return {
        "sha_git": sha_git(),
        "rama_git": rama_git(),
        "huella_datos": huella_datos(),
        "huella_entorno": huella_entorno(),
    }


if __name__ == "__main__":
    print("\nPROCEDENCIA DE ESTA EJECUCIÓN\n" + "-" * 68)
    for k, v in completa().items():
        print(f"  {k:<16} {v}")
    if "sucio" in sha_git():
        print("\n  Aviso: hay cambios sin comitear. Un modelo entrenado ahora no se puede")
        print("  reconstruir solo con el SHA. Commiteá antes de entrenar para producción.")
    print()
