# -*- coding: utf-8 -*-
"""
La política de reposición.

Lo que se comprueba aquí no es que el código corra: es que las propiedades que hacen que la
política tenga sentido sigan siendo ciertas. Si alguien cambia una fórmula y el stock de
seguridad deja de crecer con el nivel de servicio exigido, esta suite lo dice antes de que un
almacén se quede vacío.
"""
from __future__ import annotations
import numpy as np
import pytest

import politica as pol


# --------------------------------------------------------------------------- razón crítica
def test_razon_critica_caso_conocido():
    # Cu = 3, Co = 1  ->  tau* = 0,75: se exige cubrir tres cuartas partes de la distribución.
    assert pol.razon_critica(3.0, 1.0) == pytest.approx(0.75)


def test_razon_critica_simetrica():
    assert pol.razon_critica(1.0, 1.0) == pytest.approx(0.5)


def test_razon_critica_crece_con_el_coste_de_quiebre():
    anterior = 0.0
    for cu in (1.0, 2.0, 5.0, 20.0):
        actual = pol.razon_critica(cu, 1.0)
        assert actual > anterior
        anterior = actual


def test_razon_critica_rechaza_costes_imposibles():
    with pytest.raises(ValueError):
        pol.razon_critica(-1.0, 1.0)
    with pytest.raises(ValueError):
        pol.razon_critica(0.0, 0.0)


# --------------------------------------------------------------------------- niveles por categoría
def test_cada_categoria_tiene_nivel():
    for cat in ("SUPERMARKET", "ACCESORIES", "HOME_&_GARDEN"):
        assert 0.5 < pol.NIVEL_POR_CATEGORIA[cat] < 1.0


def test_el_nivel_se_lee_del_codigo_de_articulo():
    assert pol.nivel_servicio("SUPERMARKET_3_069") == 0.90
    assert pol.nivel_servicio("ACCESORIES_1_001") == 0.95
    assert pol.nivel_servicio("HOME_&_GARDEN_2_010") == 0.95


def test_lo_fresco_no_tiene_mas_nivel_que_lo_no_perecedero():
    # La merma decide: lo que se estropea no puede tener un colchón mayor que lo que se guarda.
    assert pol.nivel_servicio("SUPERMARKET_1_001") <= pol.nivel_servicio("ACCESORIES_1_001")


def test_categoria_desconocida_cae_en_el_valor_por_defecto():
    assert pol.nivel_servicio("OTRA_1_001") == pol.NIVEL_POR_DEFECTO


# --------------------------------------------------------------------------- sigma
def test_sigma_desde_cuantil_invierte_la_definicion():
    # Si media = 10 y sigma = 4, el percentil 90 está en 10 + 1,2816*4. Recuperarlo tiene que
    # devolver el 4 de partida.
    from scipy.stats import norm
    media = np.array([10.0])
    sigma = np.array([4.0])
    p90 = media + norm.ppf(0.90) * sigma
    assert pol.sigma_desde_cuantil(p90, media) == pytest.approx(sigma)


def test_sigma_nunca_negativa_aunque_los_cuantiles_se_crucen():
    # El cruce de cuantiles fue un defecto real del proyecto: 2,96% de las filas tenían p90 por
    # debajo de la media. La política no puede producir un colchón negativo ni en ese caso.
    s = pol.sigma_desde_cuantil(np.array([1.0, 5.0]), np.array([4.0, 2.0]))
    assert (s >= 0).all()


def test_agregar_sigma_usa_la_raiz_del_tiempo():
    assert pol.agregar_sigma(np.array([1.0]), 9) == pytest.approx(3.0)


def test_agregar_sigma_rechaza_ventanas_vacias():
    with pytest.raises(ValueError):
        pol.agregar_sigma(np.array([1.0]), 0)


# --------------------------------------------------------------------------- stock y nivel
def test_stock_seguridad_crece_con_el_nivel_exigido():
    sigma = np.full(4, 3.0)
    niveles = np.array([0.80, 0.85, 0.90, 0.98])
    ss = pol.stock_seguridad(sigma, niveles)
    assert (np.diff(ss) > 0).all()


def test_stock_seguridad_crece_con_la_incertidumbre():
    niveles = np.full(3, 0.95)
    ss = pol.stock_seguridad(np.array([1.0, 2.0, 4.0]), niveles)
    assert (np.diff(ss) > 0).all()


def test_stock_seguridad_nulo_cuando_no_hay_incertidumbre():
    assert pol.stock_seguridad(np.zeros(3), np.full(3, 0.95)) == pytest.approx(np.zeros(3))


def test_nivel_objetivo_nunca_por_debajo_de_la_demanda_esperada():
    d = np.array([0.0, 5.0, 100.0])
    s = np.array([1.0, 0.0, 12.0])
    n = np.full(3, 0.90)
    assert (pol.nivel_objetivo(d, s, n) >= d).all()


def test_nivel_objetivo_ignora_demandas_negativas():
    assert pol.nivel_objetivo(np.array([-5.0]), np.zeros(1), np.full(1, 0.9)) == pytest.approx([0.0])


# --------------------------------------------------------------------------- la identidad
def test_el_coste_del_vendedor_de_periodicos_es_pinball_reescalada():
    """C(S) = (Cu + Co) * L_tau*(D - S).

    Esta igualdad es el argumento central del experimento 05: elegir el modelo por coste de
    negocio y elegirlo por pérdida pinball en el cuantil correcto son la misma cosa. Si deja de
    cumplirse, medio capítulo de la memoria deja de ser cierto.
    """
    rng = np.random.default_rng(42)
    for cu, co in [(3.0, 1.0), (1.0, 1.0), (10.0, 0.5), (0.5, 4.0)]:
        objetivo = rng.uniform(0, 50, 500)
        demanda = rng.uniform(0, 50, 500)
        tau = pol.razon_critica(cu, co)
        izq = pol.coste_esperado(objetivo, demanda, cu, co)
        der = (cu + co) * pol.pinball(demanda, objetivo, tau)
        assert izq == pytest.approx(der)


def test_el_nivel_optimo_minimiza_el_coste_esperado():
    """Con demanda normal conocida, el S que minimiza el coste es el cuantil tau*.

    Se comprueba por fuerza bruta sobre una rejilla: ningún otro nivel sale más barato.
    """
    from scipy.stats import norm
    rng = np.random.default_rng(7)
    cu, co = 4.0, 1.0
    tau = pol.razon_critica(cu, co)
    demanda = rng.normal(100, 15, 200_000)
    optimo = norm.ppf(tau, 100, 15)
    coste_optimo = pol.coste_esperado(np.array([optimo]), demanda, cu, co).mean()
    for alternativo in (optimo - 10, optimo - 4, optimo + 4, optimo + 10):
        assert pol.coste_esperado(np.array([alternativo]), demanda, cu, co).mean() > coste_optimo


def test_pinball_es_el_error_absoluto_en_la_mediana():
    y = np.array([1.0, 5.0, -3.0])
    p = np.array([2.0, 2.0, 2.0])
    assert 2 * pol.pinball(y, p, 0.5) == pytest.approx(np.abs(y - p))
