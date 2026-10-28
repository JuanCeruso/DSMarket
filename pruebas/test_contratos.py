# -*- coding: utf-8 -*-
"""
Los contratos de datos.

Un contrato que nunca ha fallado no está probado: está sin estrenar. Aquí se construye un
almacén de juguete en memoria, se comprueba que pasa limpio, y luego se rompe **una cosa cada
vez** para verificar que el contrato correspondiente se entera. Es la única forma de saber que
detecta lo que dice detectar.

Dos contratos no se pueden probar así y se declaran aparte: el que exige que `dim_serie` tenga
exactamente 30.490 filas —un almacén de juguete nunca las tendrá— y el de frescura, que compara
con la fecha de hoy.
"""
from __future__ import annotations
import pytest

from contratos import CONTRATOS, BLOQUEA, AVISA

# Contratos atados al tamaño o a la fecha reales; se prueban en la ejecución de verdad, no aquí.
NO_APLICABLES = {"dim_serie completa", "frescura de los datos"}

APLICABLES = [(n, s, sql, d) for n, s, sql, d in CONTRATOS if n not in NO_APLICABLES]


def malas(con, nombre: str) -> int:
    sql = next(sql for n, _, sql, _ in CONTRATOS if n == nombre)
    return int(con.execute(sql).fetchone()[0] or 0)


# --------------------------------------------------------------------------- el catálogo
def test_el_catalogo_esta_bien_formado():
    nombres = [c[0] for c in CONTRATOS]
    assert len(nombres) == len(set(nombres)), "hay dos contratos con el mismo nombre"
    for nombre, severidad, sql, descripcion in CONTRATOS:
        assert severidad in (BLOQUEA, AVISA), f"«{nombre}» tiene una severidad desconocida"
        assert "AS malas" in sql, f"«{nombre}» no devuelve la columna 'malas'"
        assert len(descripcion) > 20, f"«{nombre}» no explica qué significa fallar"


def test_la_mayoria_de_los_contratos_bloquean():
    # Si casi todo avisa, no hay contratos: hay comprobaciones. La proporción importa.
    bloqueantes = sum(1 for c in CONTRATOS if c[1] == BLOQUEA)
    assert bloqueantes >= len(CONTRATOS) * 0.7


# --------------------------------------------------------------------------- almacén limpio
@pytest.mark.parametrize("nombre", [c[0] for c in APLICABLES])
def test_un_almacen_correcto_pasa_todos_los_contratos(almacen_falso, nombre):
    assert malas(almacen_falso, nombre) == 0


# --------------------------------------------------------------------------- roturas dirigidas
def test_detecta_una_venta_sin_precio(almacen_falso):
    almacen_falso.execute("INSERT INTO fact_ventas VALUES ('ITEM_1','T1',DATE '2016-01-02',5,NULL,7.5)")
    assert malas(almacen_falso, "sin ventas sin precio") == 1


def test_detecta_unidades_negativas(almacen_falso):
    almacen_falso.execute("INSERT INTO fact_ventas VALUES ('ITEM_1','T1',DATE '2016-01-02',-3,1.5,-4.5)")
    assert malas(almacen_falso, "unidades no negativas") == 1


def test_detecta_un_importe_que_no_cuadra(almacen_falso):
    almacen_falso.execute("UPDATE fact_ventas SET importe = 99.0 WHERE item='ITEM_1' AND store_code='T1'")
    assert malas(almacen_falso, "importe coherente") > 0


def test_detecta_un_producto_fantasma(almacen_falso):
    almacen_falso.execute("INSERT INTO fact_ventas VALUES ('ITEM_INVENTADO','T1',DATE '2016-01-02',1,1.0,1.0)")
    assert malas(almacen_falso, "integridad referencial de producto") == 1


def test_detecta_una_tienda_fantasma(almacen_falso):
    almacen_falso.execute("INSERT INTO fact_ventas VALUES ('ITEM_1','T99',DATE '2016-01-02',1,1.0,1.0)")
    assert malas(almacen_falso, "integridad referencial de tienda") == 1


def test_detecta_un_calendario_corto(almacen_falso):
    almacen_falso.execute("DELETE FROM dim_calendario WHERE fecha > DATE '2016-01-20'")
    assert malas(almacen_falso, "calendario cubre el horizonte") == 1


def test_detecta_una_prediccion_fuera_del_calendario(almacen_falso):
    almacen_falso.execute("INSERT INTO fact_predicciones VALUES "
                          "('ITEM_1','T1',DATE '2030-01-01',1.0,2.0,'mod_prueba')")
    assert malas(almacen_falso, "predicciones dentro del calendario") == 1


def test_detecta_una_prediccion_negativa(almacen_falso):
    almacen_falso.execute("UPDATE fact_predicciones SET prediccion_media = -1 "
                          "WHERE item='ITEM_1' AND store_code='T1'")
    assert malas(almacen_falso, "predicciones no negativas") > 0


def test_detecta_el_cruce_de_cuantiles(almacen_falso):
    """El defecto real: 25.296 filas con el p90 por debajo de la media.

    Lo encontró este contrato sobre el almacén de verdad, y dejaba sin colchón al 22% del
    segmento CZ, justo el de demanda más errática. Esta prueba existe para que no vuelva.
    """
    almacen_falso.execute("UPDATE fact_predicciones SET prediccion_p90 = 0.5 "
                          "WHERE item='ITEM_1' AND store_code='T1'")
    assert malas(almacen_falso, "el p90 no está por debajo de la media") > 0


def test_detecta_un_duplicado_en_el_grano(almacen_falso):
    almacen_falso.execute("INSERT INTO fact_ventas VALUES ('ITEM_1','T1',DATE '2016-01-01',2,1.5,3.0)")
    assert malas(almacen_falso, "sin duplicados en el grano") == 1


def test_detecta_el_fin_de_semana_corrido(almacen_falso):
    """El defecto real: `es_fin_de_semana` marcaba miércoles y jueves.

    La causa fue suponer que `weekday_int` era 0=lunes cuando en este calendario va 1=sábado.
    No produce excepción ni valores raros —la columna es booleana y siempre parece plausible—,
    y `is_weekend` es una de las variables del modelo. Se reproduce aquí la versión equivocada.
    """
    almacen_falso.execute("UPDATE dim_calendario SET es_fin_de_semana = (weekday_int IN (5, 6))")
    assert malas(almacen_falso, "el fin de semana cae en sábado y domingo") > 0


def test_detecta_que_la_bandera_cambie_de_significado_en_el_futuro(almacen_falso):
    """La forma peligrosa del mismo defecto: una definición para entrenar y otra para predecir.

    El modelo aprende con una y sirve con otra. No hay error, no hay alerta, y el sesgo es
    permanente. Es el motivo de que este contrato sea bloqueante y no un aviso.
    """
    almacen_falso.execute("UPDATE dim_calendario SET es_fin_de_semana = NOT es_fin_de_semana "
                          "WHERE es_futuro")
    assert malas(almacen_falso, "la bandera de fin de semana no cambia de significado en el futuro") > 0


def test_detecta_una_serie_sin_segmentar(almacen_falso):
    almacen_falso.execute("UPDATE dim_serie SET clase_xyz = NULL WHERE item='ITEM_1'")
    assert malas(almacen_falso, "cobertura de segmentación") == 2
