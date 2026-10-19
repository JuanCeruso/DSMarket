# -*- coding: utf-8 -*-
"""
DSMarket — exporta la capa gold a los CSV que importa Power BI (lakehouse/gold_csv).

Power BI Desktop lee CSV, no Parquet. Este script es el único camino de gold a gold_csv, de modo
que el panel nunca se alimenta de una copia más vieja que el almacén. Hay que ejecutarlo siempre
después de `pipeline.py`, `carga_predicciones.py`, `carga_clusters.py`, `carga_precios.py` o `carga_similitud.py`.

    fact_predicciones  se parte en 4 ficheros (una semana cada uno) por el límite de tamaño de Power BI
    fact_ventas        no se exporta: el panel usa los marts, no el grano atómico
"""
import os, time
from pipeline import conectar, GOLD, RAIZ

CSV = os.path.join(RAIZ, "gold_csv")
TABLAS = ["dim_calendario", "dim_producto", "dim_tienda", "dim_serie", "dim_arquetipo",
          "fact_reposicion", "mart_ventas_dia", "mart_producto_tienda",
          "mart_arquetipo_dia_semana", "mart_arquetipo_mes", "mart_producto_perfil",
          "mart_producto_mes", "mart_producto_top_dias",
          "mart_precios", "mart_precios_producto", "mart_precios_tienda",
          "mart_tienda_perfil", "mart_tienda_distancia"]


def columnas(con, tabla):
    """SELECT con los DOUBLE redondeados a 4 decimales: CSV más ligero y sin ruido de coma flotante."""
    cols = con.execute(f"DESCRIBE SELECT * FROM {tabla}").fetchall()
    return ", ".join(f"round({n}, 4) AS {n}" if t == "DOUBLE" else n for n, t, *_ in cols)


def main():
    con = conectar()
    os.makedirs(CSV, exist_ok=True)
    t0 = time.time()
    for t in TABLAS:
        if not os.path.exists(os.path.join(GOLD, f"{t}.parquet")):
            print(f"  {t:28s} NO EXISTE en gold: se omite")
            continue
        orden = "ORDER BY fecha_revision, serie_id" if t == "fact_reposicion" else ""
        con.execute(f"COPY (SELECT {columnas(con, t)} FROM {t} {orden}) TO '{CSV}/{t}.csv' (HEADER, DELIMITER ',')")
        n = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        print(f"  {t:28s} {n:>10,} filas")
    fechas = [r[0] for r in con.execute("SELECT DISTINCT fecha FROM fact_predicciones ORDER BY 1").fetchall()]
    por_parte = -(-len(fechas) // 4)
    for k in range(4):
        trozo = fechas[k * por_parte:(k + 1) * por_parte]
        con.execute(f"""COPY (SELECT serie_id, item, store_code, fecha, round(prediccion_media, 4) AS prediccion_media,
                                     round(prediccion_p90, 4) AS prediccion_p90
                              FROM fact_predicciones WHERE fecha BETWEEN DATE '{trozo[0]}' AND DATE '{trozo[-1]}'
                              ORDER BY serie_id, fecha)
                       TO '{CSV}/fact_predicciones_{k + 1}.csv' (HEADER, DELIMITER ',')""")
    print(f"  fact_predicciones            en 4 ficheros  ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
