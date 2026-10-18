# -*- coding: utf-8 -*-
"""Utilidades comunes de la capa de operación: rutas, conexión y escritura en el almacén."""
from __future__ import annotations
import os, json, uuid, datetime as dt
import duckdb, pandas as pd

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLD = os.path.join(RAIZ, "lakehouse", "gold")
OPER = os.path.join(GOLD, "operacion")
os.makedirs(OPER, exist_ok=True)


def ahora() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def nuevo_id(prefijo: str) -> str:
    return f"{prefijo}_{dt.datetime.now():%Y%m%d}_{uuid.uuid4().hex[:6]}"


# Límite de memoria de DuckDB. Por defecto conservador para que funcione en máquinas
# pequeñas: DuckDB vuelca a disco cuando lo necesita, así que un límite bajo cuesta tiempo,
# no errores. En un equipo holgado conviene subirlo:  export DSMARKET_MEM=8GB
MEMORIA = os.environ.get("DSMARKET_MEM", "2GB")
HILOS = os.environ.get("DSMARKET_HILOS", "4")


def conectar(vistas: bool = True):
    con = duckdb.connect()
    con.execute(f"SET memory_limit='{MEMORIA}'; SET threads={HILOS};")
    con.execute("SET preserve_insertion_order=false;")   # menos memoria en agregaciones grandes
    tmp = os.path.join(os.path.expanduser("~"), ".duckdb_tmp")
    os.makedirs(tmp, exist_ok=True)
    con.execute(f"SET temp_directory='{tmp}';")
    if vistas:
        for f in sorted(os.listdir(GOLD)):
            # Solo ficheros cuyo nombre sea un identificador válido: el nombre de la vista sale
            # del nombre del fichero, así que un «fact_predicciones.bak.parquet» se registraría
            # como la vista «fact_predicciones.bak» y DuckDB lo leería como esquema.tabla,
            # tumbando la conexión entera. Las copias de seguridad se ignoran en vez de romper.
            if f.endswith(".parquet") and f[:-8].isidentifier():
                con.execute(f"CREATE OR REPLACE VIEW {f[:-8]} AS "
                            f"SELECT * FROM read_parquet('{os.path.join(GOLD, f)}')")
    return con


def anexar(tabla: str, filas: list[dict]) -> None:
    """Añade filas a una tabla de operación, creándola si no existe.

    Se escribe con un fichero temporal y un reemplazo atómico: si el proceso muere a mitad,
    la tabla anterior sigue siendo legible. Es la razón de no escribir en el sitio.
    """
    if not filas:
        return
    destino = os.path.join(OPER, f"{tabla}.parquet")
    nuevo = pd.DataFrame(filas)
    if os.path.exists(destino):
        nuevo = pd.concat([pd.read_parquet(destino), nuevo], ignore_index=True)
    tmp = destino + ".tmp"
    nuevo.to_parquet(tmp, index=False)
    os.replace(tmp, destino)


def leer(tabla: str) -> pd.DataFrame:
    destino = os.path.join(OPER, f"{tabla}.parquet")
    return pd.read_parquet(destino) if os.path.exists(destino) else pd.DataFrame()


def json_corto(d: dict) -> str:
    return json.dumps(d, ensure_ascii=False, sort_keys=True, default=str)
