# -*- coding: utf-8 -*-
"""
DSMarket — análisis de grupos de producto (Tarea 2) en la capa gold.

Lee el perfil de comportamiento de cada producto que guarda el notebook 02
(cache_forecast/perfil_productos.csv) y las ventas de la capa silver, y escribe seis tablas:

    dim_arquetipo               ficha de los 6 grupos (tamaño, peso, comportamiento medio, mix de categorías)
    mart_producto_perfil        variables de comportamiento de cada producto
    mart_arquetipo_dia_semana   índice de venta por día de la semana y grupo (1,00 = media del grupo)
    mart_arquetipo_mes          índice de venta por mes y grupo (1,00 = media del grupo)
    mart_producto_mes           índice de venta por mes de cada producto
    mart_producto_top_dias      los 5 mejores días de cada producto

Todos los índices se calculan solo sobre los días en que el producto ya estaba a la venta
(desde su primera venta), igual que en el notebook 02.
Salida: lakehouse/gold/*.parquet y lakehouse/gold_csv/*.csv (los que importa Power BI).
"""
import os, sys, time
import duckdb

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROYECTO = os.path.dirname(RAIZ)
SILVER, GOLD, CSV = (os.path.join(RAIZ, c) for c in ("silver", "gold", "gold_csv"))
PERFIL = os.path.join(PROYECTO, "cache_forecast", "perfil_productos.csv")
DIAS = "CASE isodow(fecha) WHEN 1 THEN 'Lun' WHEN 2 THEN 'Mar' WHEN 3 THEN 'Mié' WHEN 4 THEN 'Jue' WHEN 5 THEN 'Vie' WHEN 6 THEN 'Sáb' ELSE 'Dom' END"
MESES = "CASE month(fecha) WHEN 1 THEN 'Ene' WHEN 2 THEN 'Feb' WHEN 3 THEN 'Mar' WHEN 4 THEN 'Abr' WHEN 5 THEN 'May' WHEN 6 THEN 'Jun' WHEN 7 THEN 'Jul' WHEN 8 THEN 'Ago' WHEN 9 THEN 'Sep' WHEN 10 THEN 'Oct' WHEN 11 THEN 'Nov' ELSE 'Dic' END"


def main():
    con = duckdb.connect()
    con.execute("SET memory_limit='2GB'")
    t0 = time.time()
    con.execute(f"""CREATE TEMP TABLE perfil AS
                    SELECT item, grupo, nombre_grupo AS arquetipo, category AS categoria, department AS departamento,
                           total_units, dias_activo, units_dia, zero_frac, weekend_lift, dec_lift, event_lift,
                           avg_price, facturacion
                    FROM read_csv_auto('{PERFIL}')""")
    # ventas diarias por producto (suma de las 10 tiendas), solo desde la primera venta
    con.execute(f"""CREATE TEMP TABLE dia_item AS
                    WITH d AS (SELECT item, fecha, sum(unidades) AS u FROM read_parquet('{SILVER}/ventas.parquet') GROUP BY 1, 2),
                         f AS (SELECT item, min(fecha) AS f0 FROM d WHERE u > 0 GROUP BY 1)
                    SELECT d.item, d.fecha, d.u FROM d JOIN f USING (item) WHERE d.fecha >= f.f0""")
    print(f"ventas diarias por producto: {con.execute('select count(*) from dia_item').fetchone()[0]:,} filas ({time.time()-t0:.0f}s)")

    tablas = {}
    tablas['dim_arquetipo'] = """
        SELECT grupo, arquetipo, count(*) AS productos,
               round(count(*) * 100.0 / sum(count(*)) OVER (), 2) AS pct_catalogo,
               round(sum(facturacion) * 100.0 / sum(sum(facturacion)) OVER (), 2) AS pct_facturacion,
               round(avg(units_dia), 3) AS unidades_dia, round(avg(zero_frac) * 100, 2) AS pct_dias_sin_venta,
               round(avg(weekend_lift), 4) AS fin_semana_vs_semana, round(avg(dec_lift), 4) AS diciembre_vs_resto,
               round(avg(event_lift), 4) AS eventos_vs_normal, round(avg(avg_price), 3) AS precio_medio,
               round(avg((categoria = 'ACCESORIES')::INT) * 100, 1) AS pct_accesorios,
               round(avg((categoria = 'HOME_&_GARDEN')::INT) * 100, 1) AS pct_hogar,
               round(avg((categoria = 'SUPERMARKET')::INT) * 100, 1) AS pct_alimentacion
        FROM perfil GROUP BY grupo, arquetipo ORDER BY grupo"""
    tablas['mart_producto_perfil'] = """
        SELECT item, round(total_units, 0) AS unidades_total, dias_activo, round(units_dia, 3) AS unidades_dia,
               round(zero_frac * 100, 2) AS pct_dias_sin_venta, round(weekend_lift, 4) AS fin_semana_vs_semana,
               round(dec_lift, 4) AS diciembre_vs_resto, round(event_lift, 4) AS eventos_vs_normal,
               round(avg_price, 3) AS precio_medio, round(facturacion, 2) AS facturacion
        FROM perfil ORDER BY item"""
    for nombre, expr, orden in (('mart_arquetipo_dia_semana', DIAS, 'isodow(fecha)'), ('mart_arquetipo_mes', MESES, 'month(fecha)')):
        etiqueta = 'dia_semana' if 'dia' in nombre else 'mes'
        tablas[nombre] = f"""
            WITH b AS (SELECT p.arquetipo, {expr} AS {etiqueta}, {orden} AS orden, d.u
                       FROM dia_item d JOIN perfil p USING (item)),
                 g AS (SELECT arquetipo, avg(u) AS media FROM b GROUP BY 1)
            SELECT b.arquetipo, b.{etiqueta}, b.orden, round(avg(b.u) / g.media, 4) AS indice
            FROM b JOIN g USING (arquetipo) GROUP BY b.arquetipo, b.{etiqueta}, b.orden, g.media ORDER BY 1, 3"""
    tablas['mart_producto_mes'] = f"""
        WITH b AS (SELECT item, {MESES} AS mes, month(fecha) AS orden, u FROM dia_item),
             g AS (SELECT item, avg(u) AS media FROM b GROUP BY 1)
        SELECT b.item, b.mes, b.orden, round(avg(b.u) / nullif(g.media, 0), 4) AS indice
        FROM b JOIN g USING (item) GROUP BY b.item, b.mes, b.orden, g.media ORDER BY 1, 3"""
    tablas['mart_producto_top_dias'] = """
        SELECT item, row_number() OVER (PARTITION BY item ORDER BY u DESC, fecha) AS posicion, fecha, u AS unidades
        FROM dia_item QUALIFY posicion <= 5 ORDER BY item, posicion"""
    os.makedirs(GOLD, exist_ok=True); os.makedirs(CSV, exist_ok=True)
    for nombre, sql in tablas.items():
        con.execute(f"COPY ({sql}) TO '{GOLD}/{nombre}.parquet' (FORMAT PARQUET, COMPRESSION ZSTD)")
        con.execute(f"COPY (SELECT * FROM read_parquet('{GOLD}/{nombre}.parquet')) TO '{CSV}/{nombre}.csv' (HEADER, DELIMITER ',')")
        n = con.execute(f"select count(*) from read_parquet('{GOLD}/{nombre}.parquet')").fetchone()[0]
        print(f"  {nombre:28s} {n:>8,} filas")
    print(f"listo en {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
