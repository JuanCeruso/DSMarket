# -*- coding: utf-8 -*-
"""
Configuración común de las pruebas.

Dos decisiones que explican por qué esta suite se puede ejecutar en un servidor de integración
continua donde no hay ni un byte de datos de DSMarket:

  1. **Las rutas.** `operacion/` no es un paquete instalable; sus módulos se importan entre sí
     por nombre (`from base import ...`). Se añade la carpeta al camino de importación en vez de
     reescribir veinte importaciones.
  2. **El almacén de mentira.** Los contratos de datos son SQL contra el almacén. Para probarlos
     hace falta *un* almacén, no *el* almacén: `almacen_falso` construye en memoria un DuckDB con
     las mismas tablas y cuatro filas cada una. Así se puede comprobar que un contrato detecta la
     violación que dice detectar, que es lo que en realidad se quiere saber de un contrato.
"""
from __future__ import annotations
import os, sys
import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for carpeta in ("operacion", "avanzado", "app"):
    ruta = os.path.join(RAIZ, carpeta)
    if os.path.isdir(ruta) and ruta not in sys.path:
        sys.path.insert(0, ruta)


@pytest.fixture
def almacen_falso():
    """Un almacén mínimo, en memoria, que pasa todos los contratos.

    Cada prueba lo rompe a propósito de una manera distinta y comprueba que el contrato
    correspondiente se entera. Es deliberadamente diminuto: 2 productos x 2 tiendas x 3 días.
    """
    duckdb = pytest.importorskip("duckdb")
    con = duckdb.connect()
    con.execute("""
        CREATE TABLE dim_producto AS SELECT * FROM (VALUES
            ('ITEM_1','cat_a','dep_a'), ('ITEM_2','cat_a','dep_a')
        ) t(item, category, department);

        CREATE TABLE dim_tienda AS SELECT * FROM (VALUES
            ('T1','ciudad_a'), ('T2','ciudad_a')
        ) t(store_code, region);

        CREATE TABLE dim_calendario AS
            SELECT DATE '2016-01-01' + INTERVAL (i) DAY              AS fecha,
                   (i % 7) + 1                                       AS weekday_int,
                   dayname(DATE '2016-01-01' + INTERVAL (i) DAY)     AS dia_semana,
                   -- Se deriva del nombre del día, igual que en el almacén de verdad. Ponerlo
                   -- aquí como «weekday_int IN (5,6)» reproduciría el defecto y la prueba
                   -- pasaría comprobando que el error es consistente consigo mismo.
                   dayofweek(DATE '2016-01-01' + INTERVAL (i) DAY) IN (0, 6) AS es_fin_de_semana,
                   i >= 3                                            AS es_futuro
            FROM range(0, 35) t(i);

        CREATE TABLE fact_ventas AS
            SELECT p.item, s.store_code, c.fecha,
                   2.0::DOUBLE AS unidades, 1.5::DOUBLE AS precio, 3.0::DOUBLE AS importe
            FROM dim_producto p CROSS JOIN dim_tienda s
            CROSS JOIN (SELECT fecha FROM dim_calendario WHERE NOT es_futuro) c;

        CREATE TABLE dim_serie AS
            SELECT item, store_code, 'A' AS clase_abc, 'X' AS clase_xyz,
                   2.0::DOUBLE AS media_dia, 0.5::DOUBLE AS desvio_dia
            FROM dim_producto CROSS JOIN dim_tienda;

        CREATE TABLE fact_predicciones AS
            SELECT s.item, s.store_code, c.fecha,
                   2.0::DOUBLE AS prediccion_media, 3.0::DOUBLE AS prediccion_p90,
                   'mod_prueba' AS modelo_id
            FROM dim_serie s
            CROSS JOIN (SELECT fecha FROM dim_calendario WHERE es_futuro LIMIT 28) c;
    """)
    yield con
    con.close()
