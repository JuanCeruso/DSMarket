# -*- coding: utf-8 -*-
"""
La puerta de promoción.

Es la pieza que decide qué modelo llega a producción, así que sus reglas se prueban una por una,
incluida la que más importa: que un candidato peor **no** pase.
"""
from __future__ import annotations
import pytest

from promocion import evaluar, COBERTURA_MIN, COBERTURA_MAX, MARGEN_MAE


def modelo(mae=4.0, cobertura=0.90, sha="abc123def456"):
    return {"modelo_id": "mod_x", "metrica_mae_validacion": mae,
            "metrica_cobertura_p90": cobertura, "sha_git": sha}


def evaluar_sin_contratos(cand, vig, margen=MARGEN_MAE, exigir_limpio=False, monkeypatch=None):
    """Los contratos necesitan el almacén; aquí se prueban las reglas de la puerta, no los datos."""
    pasa, fallos, avisos = evaluar(cand, vig, margen, exigir_limpio)
    fallos = [f for f in fallos if "contratos" not in f]
    return (not fallos), fallos, avisos


def test_un_candidato_mejor_pasa():
    pasa, fallos, _ = evaluar_sin_contratos(modelo(mae=3.5), modelo(mae=4.0))
    assert pasa, fallos


def test_un_candidato_algo_peor_pasa_por_el_margen_de_ruido():
    # 2% peor: dentro del margen del 5%. La puerta no puede bloquear el ruido de validación.
    pasa, fallos, _ = evaluar_sin_contratos(modelo(mae=4.08), modelo(mae=4.0))
    assert pasa, fallos


def test_un_candidato_claramente_peor_no_pasa():
    pasa, fallos, _ = evaluar_sin_contratos(modelo(mae=4.8), modelo(mae=4.0))
    assert not pasa
    assert any("MAE" in f for f in fallos)


def test_el_margen_es_configurable_y_muerde():
    pasa, _, _ = evaluar_sin_contratos(modelo(mae=4.08), modelo(mae=4.0), margen=0.01)
    assert not pasa


def test_una_cobertura_demasiado_baja_no_pasa():
    pasa, fallos, _ = evaluar_sin_contratos(modelo(cobertura=0.70), modelo())
    assert not pasa
    assert any("cobertura" in f for f in fallos)


def test_una_cobertura_demasiado_alta_tampoco_pasa():
    # Un intervalo que cubre el 99% no es prudencia: es stock de seguridad inflado en todo el
    # surtido. La banda tiene dos lados a propósito.
    pasa, fallos, _ = evaluar_sin_contratos(modelo(cobertura=0.99), modelo())
    assert not pasa
    assert any("cobertura" in f for f in fallos)


@pytest.mark.parametrize("cobertura", [COBERTURA_MIN, 0.90, COBERTURA_MAX])
def test_la_banda_de_cobertura_incluye_sus_extremos(cobertura):
    pasa, fallos, _ = evaluar_sin_contratos(modelo(cobertura=cobertura), modelo())
    assert pasa, fallos


def test_el_primer_modelo_pasa_si_es_sensato():
    pasa, fallos, avisos = evaluar_sin_contratos(modelo(), None)
    assert pasa, fallos
    assert any("primero" in a for a in avisos)


def test_el_primer_modelo_no_pasa_si_no_es_sensato():
    pasa, _, _ = evaluar_sin_contratos(modelo(cobertura=0.40), None)
    assert not pasa


def test_un_candidato_sin_mae_no_pasa():
    cand = modelo(); cand.pop("metrica_mae_validacion")
    pasa, fallos, _ = evaluar_sin_contratos(cand, modelo())
    assert not pasa
    assert any("MAE" in f for f in fallos)


def test_el_arbol_sucio_avisa_por_defecto_y_rechaza_si_se_exige():
    pasa, fallos, avisos = evaluar_sin_contratos(modelo(sha="abc123+sucio"), modelo())
    assert pasa
    assert any("sin comitear" in a for a in avisos)

    pasa, fallos, _ = evaluar_sin_contratos(modelo(sha="abc123+sucio"), modelo(), exigir_limpio=True)
    assert not pasa
    assert any("sin comitear" in f for f in fallos)
