# -*- coding: utf-8 -*-
"""
Las métricas de monitorización.

El índice de estabilidad de población decide si el sistema entra en alerta. Una métrica que
decide algo tiene que estar probada: aquí se comprueba que vale cero cuando no hay deriva, que
crece cuando la hay, y que no se inventa una alerta con muestras pequeñas.
"""
from __future__ import annotations
import numpy as np
import pytest

from monitor import psi


def test_psi_es_cero_sobre_la_misma_distribucion():
    rng = np.random.default_rng(0)
    x = rng.normal(0, 1, 20_000)
    y = rng.normal(0, 1, 20_000)
    assert psi(x, y) < 0.02


def test_psi_es_exactamente_cero_sobre_la_misma_muestra():
    rng = np.random.default_rng(1)
    x = rng.normal(0, 1, 5_000)
    assert psi(x, x) == pytest.approx(0.0, abs=1e-9)


def test_psi_crece_al_desplazar_la_distribucion():
    rng = np.random.default_rng(2)
    base = rng.normal(0, 1, 30_000)
    anterior = -1.0
    for desplazamiento in (0.0, 0.2, 0.5, 1.0, 2.0):
        v = psi(base, rng.normal(desplazamiento, 1, 30_000))
        assert v > anterior
        anterior = v


def test_psi_detecta_el_cambio_de_escala_aunque_la_media_no_cambie():
    # Una distribución que se ensancha sin moverse de sitio es una deriva real, y la media no la
    # ve. Es el caso que justifica usar PSI y no un simple contraste de medias.
    rng = np.random.default_rng(3)
    base = rng.normal(0, 1, 30_000)
    assert psi(base, rng.normal(0, 3, 30_000)) > 0.25


def test_psi_es_simetrico_en_la_practica():
    rng = np.random.default_rng(4)
    a = rng.normal(0, 1, 20_000)
    b = rng.normal(0.5, 1, 20_000)
    assert psi(a, b) == pytest.approx(psi(b, a), rel=0.15)


def test_psi_se_abstiene_con_muestras_pequenas():
    # Con cincuenta observaciones cualquier métrica de deriva es ruido. Devolver NaN es lo
    # correcto: el monitor trata NaN como «no se puede decir», no como «todo bien».
    rng = np.random.default_rng(5)
    assert np.isnan(psi(rng.normal(size=50), rng.normal(size=50)))


def test_psi_no_estalla_con_una_variable_constante():
    x = np.full(5_000, 7.0)
    v = psi(x, x)
    assert np.isfinite(v) and v == pytest.approx(0.0, abs=1e-9)


def test_psi_ignora_los_valores_no_finitos():
    rng = np.random.default_rng(6)
    limpio = rng.normal(0, 1, 10_000)
    sucio = np.concatenate([limpio, np.full(500, np.nan), np.full(500, np.inf)])
    assert psi(limpio, sucio) == pytest.approx(psi(limpio, limpio), abs=0.01)
