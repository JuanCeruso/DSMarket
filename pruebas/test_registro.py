# -*- coding: utf-8 -*-
"""
El registro de modelos y su ciclo de estados.

Se prueba contra un directorio temporal: `base.OPER` se reapunta antes de importar nada que
escriba, de modo que ninguna prueba toca el almacén de verdad.
"""
from __future__ import annotations
import importlib, os
import pytest


@pytest.fixture
def registro(tmp_path, monkeypatch):
    """Un registro de modelos vacío, aislado, en un directorio temporal."""
    import base
    monkeypatch.setattr(base, "OPER", str(tmp_path))
    import modelos
    importlib.reload(modelos)
    monkeypatch.setattr(modelos, "OPER", str(tmp_path))
    # `anexar` y `leer` resuelven la ruta al llamarse, así que basta con parchear base.OPER.
    monkeypatch.setattr("modelos.procedencia.completa",
                        lambda: {"sha_git": "abc123", "rama_git": "main",
                                 "huella_datos": "0" * 16, "huella_entorno": "pruebas"})
    return modelos


def alta(reg, mae=4.0, cobertura=0.90):
    return reg.registrar(tipo="lightgbm_bloques", hiperparametros={"a": 1}, ventana_dias=180,
                         fecha_corte="2016-04-24",
                         metricas={"mae_validacion": mae, "cobertura_p90": cobertura})


def test_entrenar_no_promueve(registro):
    mid = alta(registro)
    assert registro.vigente() is None, "un modelo recién entrenado no puede estar mandando"
    assert registro.candidato()["modelo_id"] == mid


def test_promover_hace_vigente_al_candidato(registro):
    mid = alta(registro)
    registro.promover(mid, "prueba")
    assert registro.vigente()["modelo_id"] == mid
    assert registro.candidato() is None


def test_solo_hay_un_vigente_por_tipo(registro):
    primero = alta(registro, mae=4.0)
    registro.promover(primero, "primero")
    segundo = alta(registro, mae=3.5)
    registro.promover(segundo, "segundo")

    h = registro.historial("lightgbm_bloques")
    assert (h["estado"] == registro.VIGENTE).sum() == 1
    assert registro.vigente()["modelo_id"] == segundo


def test_el_rechazado_queda_en_el_registro(registro):
    mid = alta(registro)
    registro.rechazar(mid, "cobertura fuera de banda")
    h = registro.historial("lightgbm_bloques")
    assert len(h) == 1, "un rechazo no borra: el histórico de lo que no pasó también informa"
    assert h["estado"].iloc[0] == registro.RECHAZADO
    assert "cobertura" in h["motivo"].iloc[0]


def test_retroceder_vuelve_al_anterior(registro):
    primero = alta(registro, mae=4.0)
    registro.promover(primero, "primero")
    segundo = alta(registro, mae=3.5)
    registro.promover(segundo, "segundo")

    vuelto = registro.retroceder()
    assert vuelto == primero
    assert registro.vigente()["modelo_id"] == primero


def test_retroceder_sin_historia_falla_claro(registro):
    mid = alta(registro)
    registro.promover(mid, "el único")
    with pytest.raises(SystemExit):
        registro.retroceder()


def test_la_promocion_actualiza_el_puntero_que_lee_predecir(registro, tmp_path):
    mid = alta(registro)
    registro.promover(mid, "prueba")
    puntero = os.path.join(str(tmp_path), "modelos", "vigente.txt")
    assert os.path.exists(puntero)
    assert open(puntero).read().strip() == mid


def test_cada_modelo_guarda_su_procedencia(registro):
    alta(registro)
    fila = registro.historial("lightgbm_bloques").iloc[0]
    for columna in ("sha_git", "huella_datos", "huella_entorno"):
        assert fila[columna], f"falta {columna}: el modelo no sería reproducible"


def test_un_registro_viejo_sin_estados_se_lee_igual(registro):
    """Compatibilidad: los registros escritos antes de que existieran los estados."""
    import pandas as pd
    from base import anexar
    anexar("dim_modelo", [{"modelo_id": "mod_viejo", "momento_entrenamiento": "2016-01-01T00:00:00",
                           "tipo": "lightgbm_bloques", "vigente": True,
                           "metrica_mae_validacion": 4.2}])
    v = registro.vigente()
    assert v is not None and v["modelo_id"] == "mod_viejo"
