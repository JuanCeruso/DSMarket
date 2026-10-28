# -*- coding: utf-8 -*-
"""
Lectura de la historia reciente de ventas, compartida por todos los consumidores de la política.

La API, la app, la etapa de reposición y la carga del almacén necesitan la misma matriz
(series x últimos días) para calcular el percentil empírico de las series estables. Está aquí, en
un solo sitio, para que los cuatro lean los mismos datos del mismo modo.
"""
from __future__ import annotations
import os
import numpy as np, pandas as pd, duckdb

from politica import VENTANA_HISTORIA


def historia_reciente(gold: str, dias: int = VENTANA_HISTORIA) -> tuple[dict, np.ndarray]:
    """Ventas de los últimos `dias` días del almacén: ({serie_id: fila}, matriz float32)."""
    con = duckdb.connect()
    ruta = os.path.join(gold, "fact_ventas.parquet")
    df = con.execute(f"""
        WITH u AS (SELECT max(fecha) AS ultima FROM read_parquet('{ruta}'))
        SELECT item || '|' || store_code AS serie_id,
               date_diff('day', fecha, u.ultima) AS atras, unidades
        FROM read_parquet('{ruta}'), u
        WHERE fecha > u.ultima - INTERVAL {int(dias)} DAY
    """).df()
    con.close()
    codigos, ids = pd.factorize(df["serie_id"])
    matriz = np.zeros((len(ids), dias), dtype=np.float32)
    matriz[codigos, dias - 1 - df["atras"].to_numpy()] = df["unidades"].to_numpy(np.float32)
    return {s: i for i, s in enumerate(ids)}, matriz
