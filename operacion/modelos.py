# -*- coding: utf-8 -*-
"""
Registro de modelos: saber qué modelo produjo qué predicción.

Sin esto, una predicción es un número sin procedencia. Con esto se puede responder la pregunta
que tarde o temprano hace alguien: «este pedido de hace tres semanas, ¿con qué modelo se
calculó, entrenado con qué datos y con qué error de validación?».

Es una tabla y una clave ajena. Cuesta una tarde y es la diferencia entre poder auditar una
decisión pasada y no poder.
"""
from __future__ import annotations
import pandas as pd
from base import anexar, leer, ahora, nuevo_id, json_corto


def registrar(tipo: str, hiperparametros: dict, ventana_dias: int,
              fecha_corte, metricas: dict, notas: str = "") -> str:
    """Da de alta un modelo entrenado y devuelve su identificador."""
    modelo_id = nuevo_id("mod")
    anexar("dim_modelo", [{
        "modelo_id": modelo_id,
        "momento_entrenamiento": ahora(),
        "tipo": tipo,
        "hiperparametros": json_corto(hiperparametros),
        "ventana_entrenamiento_dias": ventana_dias,
        "fecha_corte": str(fecha_corte),
        **{f"metrica_{k}": v for k, v in metricas.items()},
        "notas": notas,
        "vigente": True,
    }])
    _retirar_anteriores(modelo_id, tipo)
    return modelo_id


def _retirar_anteriores(modelo_id: str, tipo: str) -> None:
    """Solo un modelo por tipo queda marcado como vigente."""
    df = leer("dim_modelo")
    if df.empty:
        return
    df.loc[(df["tipo"] == tipo) & (df["modelo_id"] != modelo_id), "vigente"] = False
    import os
    from base import OPER
    tmp = os.path.join(OPER, "dim_modelo.parquet.tmp")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, os.path.join(OPER, "dim_modelo.parquet"))


def vigente(tipo: str) -> dict | None:
    df = leer("dim_modelo")
    if df.empty:
        return None
    f = df[(df["tipo"] == tipo) & (df["vigente"])]
    return f.iloc[-1].to_dict() if len(f) else None


def historial(tipo: str | None = None) -> pd.DataFrame:
    df = leer("dim_modelo")
    if df.empty or tipo is None:
        return df
    return df[df["tipo"] == tipo]


if __name__ == "__main__":
    df = leer("dim_modelo")
    if df.empty:
        print("No hay modelos registrados todavía.")
    else:
        cols = [c for c in ["modelo_id", "momento_entrenamiento", "tipo",
                            "ventana_entrenamiento_dias", "fecha_corte", "vigente"] if c in df]
        met = [c for c in df.columns if c.startswith("metrica_")]
        print(df[cols + met].to_string(index=False))
