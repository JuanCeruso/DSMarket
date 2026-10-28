# -*- coding: utf-8 -*-
"""
DSMarket — análisis de precios (EDA, sección de precios) en la capa gold.

Escribe tres tablas a partir de los precios alineados de silver:

    mart_precios            precio medio de cada serie (producto × tienda)
    mart_precios_producto   por producto: precio mínimo y máximo entre tiendas, dispersión y qué
                            tienda es la más barata y la más cara
    mart_precios_tienda     por tienda: índice de precio (% sobre la media del producto en las
                            10 tiendas) y % de productos en que es más cara que esa media

Hasta ahora estos CSV existían solo como ficheros sueltos; con este script se regeneran junto
con el resto del almacén y los números del panel «Precios» son reproducibles.

Salida: lakehouse/gold/*.parquet y lakehouse/gold_csv/*.csv
"""
import os
from pipeline import conectar, GOLD, RAIZ

CSV = os.path.join(RAIZ, "gold_csv")


def main():
    con = conectar()
    tablas = {}
    tablas["mart_precios"] = """
        SELECT item || '|' || store_code AS serie_id, item, store_code, round(avg(precio), 4) AS precio_medio
        FROM precios GROUP BY item, store_code ORDER BY item, store_code"""
    tablas["mart_precios_producto"] = """
        WITH b AS (SELECT m.item, d.categoria, d.departamento, m.store_code, m.precio_medio
                   FROM mart_precios m JOIN dim_producto d USING (item))
        SELECT item, categoria, departamento,
               min(precio_medio) AS precio_min, max(precio_medio) AS precio_max,
               round((max(precio_medio) / min(precio_medio) - 1) * 100, 4) AS dispersion_pct,
               arg_min(store_code, precio_medio) AS tienda_mas_barata,
               arg_max(store_code, precio_medio) AS tienda_mas_cara
        FROM b GROUP BY item, categoria, departamento ORDER BY dispersion_pct DESC, item"""
    tablas["mart_precios_tienda"] = """
        WITH b AS (SELECT store_code, precio_medio, avg(precio_medio) OVER (PARTITION BY item) AS media_item
                   FROM mart_precios)
        SELECT store_code,
               round(avg((precio_medio / media_item - 1) * 100), 4) AS indice_precio_pct,
               round(avg((precio_medio > media_item)::INT) * 100, 2) AS pct_productos_mas_caros
        FROM b GROUP BY store_code ORDER BY store_code"""
    os.makedirs(CSV, exist_ok=True)
    for nombre, sql in tablas.items():
        con.execute(f"COPY ({sql}) TO '{GOLD}/{nombre}.parquet' (FORMAT PARQUET, COMPRESSION ZSTD)")
        con.execute(f"CREATE OR REPLACE VIEW {nombre} AS SELECT * FROM read_parquet('{GOLD}/{nombre}.parquet')")
        con.execute(f"COPY (SELECT * FROM {nombre}) TO '{CSV}/{nombre}.csv' (HEADER, DELIMITER ',')")
        n = con.execute(f"SELECT count(*) FROM {nombre}").fetchone()[0]
        print(f"  {nombre:24s} {n:>8,} filas")


if __name__ == "__main__":
    main()
