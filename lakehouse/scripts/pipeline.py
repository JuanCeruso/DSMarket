# -*- coding: utf-8 -*-
"""
DSMarket — pipeline del lakehouse (arquitectura medallón).

    bronze/  copia fiel de las fuentes, sin transformar (trazabilidad)
    silver/  datos limpios, tipados y en formato largo (una fila por hecho)
    gold/    modelo dimensional listo para consumo (BI, API, modelos)

Motor: DuckDB sobre ficheros Parquet. La elección es deliberada — el mismo SQL
corre sin cambios sobre Fabric, BigQuery o Snowflake cambiando la conexión.

Uso:  python3 pipeline.py [bronze|silver|gold|all]
"""
import os, sys, time, logging
import duckdb

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROYECTO = os.path.dirname(RAIZ)
FUENTES = os.path.join(PROYECTO, "data_dsmarket", "data_dsmarket")
BRONZE, SILVER, GOLD = (os.path.join(RAIZ, c) for c in ("bronze", "silver", "gold"))
CACHE = os.path.join(PROYECTO, "cache_forecast")

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("pipeline")

def conectar(con_vistas=True):
    """Motor sin estado sobre almacenamiento abierto.

    El almacén ES el conjunto de ficheros Parquet: no hay base de datos propietaria que
    mantener ni migrar. DuckDB actúa como motor de consulta efímero que se levanta,
    registra las vistas y se apaga. Es el mismo principio de separación
    almacenamiento/cómputo de Fabric (OneLake), BigQuery o Snowflake — y es lo que hace
    que migrar sea cambiar el motor, no reescribir los datos.
    """
    con = duckdb.connect()                       # en memoria: el estado vive en Parquet
    con.execute("SET memory_limit='2GB'; SET threads=4;")
    # los temporales van fuera del árbol del proyecto: la carpeta sincronizada no permite borrarlos
    tmp = os.path.join(os.path.expanduser("~"), ".duckdb_tmp")
    os.makedirs(tmp, exist_ok=True)
    con.execute(f"SET temp_directory='{tmp}';")
    if con_vistas:
        registrar_vistas(con)
    return con

def registrar_vistas(con):
    """Publica cada Parquet de silver y gold como una vista consultable por su nombre."""
    for carpeta in (SILVER, GOLD):
        if not os.path.isdir(carpeta): continue
        for f in sorted(os.listdir(carpeta)):
            if f.endswith(".parquet"):
                con.execute(f"CREATE OR REPLACE VIEW {f[:-8]} AS "
                            f"SELECT * FROM read_parquet('{os.path.join(carpeta, f)}')")

def _volcar(con, sql, destino, etiqueta):
    t0 = time.time()
    con.execute(f"COPY ({sql}) TO '{destino}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    filas = con.execute(f"SELECT count(*) FROM read_parquet('{destino}')").fetchone()[0]
    mb = os.path.getsize(destino) / 1e6
    log.info(f"  {etiqueta:34s} {filas:>12,} filas  {mb:7.1f} MB  ({time.time()-t0:.0f}s)")

# ---------------------------------------------------------------- BRONZE
def bronze(con):
    """Copia fiel de las fuentes a Parquet. No se transforma nada: es la capa de trazabilidad."""
    log.info("BRONZE — ingesta sin transformación")
    for fichero, nombre in [("item_sales.csv", "item_sales"), ("item_prices.csv", "item_prices"),
                            ("daily_calendar_with_events.csv", "daily_calendar")]:
        _volcar(con, f"SELECT * FROM read_csv_auto('{os.path.join(FUENTES, fichero)}')",
                os.path.join(BRONZE, f"{nombre}.parquet"), nombre)

# ---------------------------------------------------------------- SILVER
def silver(con):
    """Limpieza, tipado y paso a formato largo. Aquí viven las reglas de negocio del EDA."""
    log.info("SILVER — limpieza y normalización")

    # calendario: se enriquece con los eventos derivados por regla de fecha (EDA, sección 11)
    _volcar(con, f"""
        WITH base AS (
            SELECT d, CAST(date AS DATE) AS fecha, weekday, weekday_int, event AS evento_origen
            FROM read_parquet('{BRONZE}/daily_calendar.parquet')
        ),
        thanksgiving AS (SELECT fecha FROM base WHERE evento_origen = 'Thanksgiving')
        SELECT b.d, b.fecha, b.weekday, b.weekday_int,
               CASE
                 WHEN month(b.fecha) = 12 AND day(b.fecha) = 25 THEN 'Christmas'
                 WHEN month(b.fecha) = 9 AND dayofweek(b.fecha) = 1 AND day(b.fecha) <= 7 THEN 'Labor Day'
                 ELSE b.evento_origen
               END AS evento,
               b.weekday_int IN (5, 6) AS es_fin_de_semana,
               year(b.fecha) AS anio, month(b.fecha) AS mes, week(b.fecha) AS semana_iso,
               -- día de cierre conocido: la tienda no abre (hallazgo de la Tarea 3)
               (month(b.fecha) = 12 AND day(b.fecha) = 25)
                 OR b.evento_origen = 'Thanksgiving' AS es_dia_cierre
        FROM base b ORDER BY b.fecha
    """, f"{SILVER}/calendario.parquet", "calendario")

    # ventas: de 1.913 columnas de día a formato largo (una fila por producto-tienda-día)
    _volcar(con, f"""
        WITH largo AS (
            UNPIVOT (SELECT * FROM read_parquet('{BRONZE}/item_sales.parquet'))
            ON COLUMNS('^d_[0-9]+$') INTO NAME d VALUE unidades
        )
        SELECT l.item, l.store_code, c.fecha, CAST(l.unidades AS SMALLINT) AS unidades
        FROM largo l JOIN read_parquet('{SILVER}/calendario.parquet') c USING (d)
    """, f"{SILVER}/ventas.parquet", "ventas (formato largo)")

    # precios: el archivo empieza 5 semanas ANTES que las ventas (hallazgo de la Tarea 3).
    # Se alinea por rango de semana anclado al final y se descartan las semanas sin etiqueta.
    _volcar(con, f"""
        WITH etiquetadas AS (
            SELECT * FROM read_parquet('{BRONZE}/item_prices.parquet') WHERE yearweek IS NOT NULL
        ),
        semanas AS (
            SELECT yearweek, dense_rank() OVER (ORDER BY yearweek) - 1 AS idx_bruto
            FROM (SELECT DISTINCT yearweek FROM etiquetadas)
        ),
        desfase AS (
            SELECT (SELECT count(*) FROM semanas)
                 - (SELECT ceil(count(*) / 7.0) FROM read_parquet('{SILVER}/calendario.parquet')) AS n
        ),
        cal_semana AS (
            SELECT fecha, CAST(floor((row_number() OVER (ORDER BY fecha) - 1) / 7) AS INTEGER) AS idx_semana
            FROM read_parquet('{SILVER}/calendario.parquet')
        )
        SELECT e.item, e.store_code, cs.fecha, CAST(e.sell_price AS DECIMAL(8,3)) AS precio
        FROM etiquetadas e
        JOIN semanas s USING (yearweek)
        CROSS JOIN desfase df
        JOIN cal_semana cs ON cs.idx_semana = s.idx_bruto - df.n
    """, f"{SILVER}/precios.parquet", "precios (alineados a día)")

    con.execute(f"""
        SELECT count(*) AS ventas_sin_precio FROM read_parquet('{SILVER}/ventas.parquet') v
        LEFT JOIN read_parquet('{SILVER}/precios.parquet') p USING (item, store_code, fecha)
        WHERE v.unidades > 0 AND p.precio IS NULL
    """)
    n = con.fetchone()[0]
    log.info(f"  control de calidad: ventas>0 sin precio = {n:,} (debe ser 0 si el alineado es correcto)")


# ---------------------------------------------------------------- GOLD
def gold(con):
    """Modelo dimensional en estrella, listo para BI, API y modelos."""
    log.info("GOLD — modelo dimensional")

    # La dimensión de fecha cubre el histórico MÁS el horizonte de predicción (28 días). Si no,
    # las relaciones de PowerBI contra fact_predicciones dejan fechas en blanco.
    _volcar(con, f"""
        WITH hist AS (SELECT * FROM read_parquet('{SILVER}/calendario.parquet')),
             rango AS (SELECT min(fecha) AS desde, max(fecha) + INTERVAL 28 DAY AS hasta FROM hist),
             espina AS (SELECT unnest(generate_series(
                            (SELECT desde FROM rango), (SELECT hasta FROM rango), INTERVAL 1 DAY
                        ))::DATE AS fecha)
        SELECT e.fecha, h.d AS dia_id, h.weekday AS dia_semana, h.weekday_int,
               year(e.fecha) AS anio, month(e.fecha) AS mes, week(e.fecha) AS semana_iso,
               h.evento,
               coalesce(h.es_fin_de_semana, dayofweek(e.fecha) IN (0, 6)) AS es_fin_de_semana,
               coalesce(h.es_dia_cierre, FALSE) AS es_dia_cierre,
               month(e.fecha) IN (11, 12) AS es_temporada_alta,
               h.d IS NULL AS es_futuro
        FROM espina e LEFT JOIN hist h USING (fecha)
        ORDER BY e.fecha
    """, f"{GOLD}/dim_calendario.parquet", "dim_calendario (con horizonte)")

    _volcar(con, f"""
        WITH prod AS (SELECT DISTINCT item, category AS categoria, department AS departamento
                      FROM read_parquet('{BRONZE}/item_sales.parquet')),
             cl AS (SELECT * FROM read_csv_auto('{CACHE}/clusters_producto.csv'))
        SELECT p.item, p.categoria, p.departamento, cl.cluster_k5, cl.cluster_k10,
               CASE cl.cluster_k5 WHEN 0 THEN 'Premium/accesorios' WHEN 1 THEN 'Núcleo estable'
                    WHEN 2 THEN 'Cola larga/eventos' WHEN 3 THEN 'Fin de semana/hogar'
                    WHEN 4 THEN 'Fin de año' END AS arquetipo
        FROM prod p LEFT JOIN cl ON cl.item = p.item
    """, f"{GOLD}/dim_producto.parquet", "dim_producto")

    _volcar(con, f"""
        WITH t AS (SELECT DISTINCT store_code, store AS tienda, region AS ciudad
                   FROM read_parquet('{BRONZE}/item_sales.parquet')),
             cl AS (SELECT * FROM read_csv_auto('{CACHE}/clusters_tienda.csv'))
        SELECT t.store_code, t.tienda, t.ciudad,
               'Grupo ' || chr(CAST(65 + cl.cluster_k3 AS INTEGER)) AS grupo_comportamiento
        FROM t LEFT JOIN cl USING (store_code)
    """, f"{GOLD}/dim_tienda.parquet", "dim_tienda")

    # tabla de hechos atómica: una fila por producto-tienda-día, valorizada
    _volcar(con, f"""
        SELECT v.fecha, v.item, v.store_code, v.unidades, p.precio,
               ROUND(v.unidades * p.precio, 2) AS importe
        FROM read_parquet('{SILVER}/ventas.parquet') v
        LEFT JOIN read_parquet('{SILVER}/precios.parquet') p USING (item, store_code, fecha)
    """, f"{GOLD}/fact_ventas.parquet", "fact_ventas (grano atómico)")

    # dimensión de serie: el grano sobre el que se decide la reposición
    ultima = con.execute(f"SELECT max(fecha) FROM read_parquet('{SILVER}/ventas.parquet')").fetchone()[0]
    _volcar(con, f"""
        WITH v90 AS (
            SELECT item, store_code, sum(unidades) AS unidades_90d,
                   sum(importe) AS facturacion_90d, avg(unidades) AS media_dia,
                   stddev_pop(unidades) AS desvio_dia,
                   sum(CASE WHEN unidades = 0 THEN 1 ELSE 0 END)::DOUBLE / count(*) AS frac_dias_sin_venta
            FROM read_parquet('{GOLD}/fact_ventas.parquet')
            WHERE fecha > DATE '{ultima}' - INTERVAL 90 DAY
            GROUP BY 1, 2
        ),
        abc AS (
            SELECT *, sum(facturacion_90d) OVER (ORDER BY facturacion_90d DESC
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
                      / sum(facturacion_90d) OVER () AS acumulado
            FROM v90
        )
        SELECT a.item || '|' || a.store_code AS serie_id,
               a.item, a.store_code, a.unidades_90d, a.facturacion_90d,
               a.media_dia, a.desvio_dia, a.frac_dias_sin_venta,
               CASE WHEN a.media_dia > 0 THEN a.desvio_dia / a.media_dia ELSE 99 END AS coef_variacion,
               CASE WHEN a.acumulado <= 0.80 THEN 'A' WHEN a.acumulado <= 0.95 THEN 'B' ELSE 'C' END AS clase_abc,
               CASE WHEN a.media_dia > 0 AND a.desvio_dia / a.media_dia <= 1.0 THEN 'X'
                    WHEN a.media_dia > 0 AND a.desvio_dia / a.media_dia <= 2.0 THEN 'Y' ELSE 'Z' END AS clase_xyz
        FROM abc a
    """, f"{GOLD}/dim_serie.parquet", "dim_serie (ABC/XYZ)")

    # marts pre-agregados para el dashboard (PowerBI no necesita el grano atómico)
    _volcar(con, f"""
        SELECT f.fecha, f.store_code, t.ciudad, t.tienda, p.categoria, p.departamento,
               sum(f.unidades) AS unidades, sum(f.importe) AS importe
        FROM read_parquet('{GOLD}/fact_ventas.parquet') f
        JOIN read_parquet('{GOLD}/dim_tienda.parquet') t USING (store_code)
        JOIN read_parquet('{GOLD}/dim_producto.parquet') p USING (item)
        GROUP BY ALL
    """, f"{GOLD}/mart_ventas_dia.parquet", "mart_ventas_dia (para BI)")

    _volcar(con, f"""
        SELECT f.item || '|' || f.store_code AS serie_id,
               f.item, f.store_code, p.arquetipo, p.categoria, p.departamento, t.ciudad, t.tienda,
               sum(f.unidades) AS unidades_total, sum(f.importe) AS facturacion_total,
               avg(f.precio) AS precio_medio
        FROM read_parquet('{GOLD}/fact_ventas.parquet') f
        JOIN read_parquet('{GOLD}/dim_tienda.parquet') t USING (store_code)
        JOIN read_parquet('{GOLD}/dim_producto.parquet') p USING (item)
        GROUP BY ALL
    """, f"{GOLD}/mart_producto_tienda.parquet", "mart_producto_tienda (para BI)")

    registrar_vistas(con)
    log.info("  vistas registradas sobre los Parquet de gold")

if __name__ == "__main__":
    etapa = sys.argv[1] if len(sys.argv) > 1 else "all"
    con = conectar()
    if etapa in ("bronze", "all"): bronze(con)
    if etapa in ("silver", "all"): silver(con)
    if etapa in ("gold", "all"): gold(con)
    con.close()
    log.info("listo")
