# -*- coding: utf-8 -*-
"""
Registro de modelos: saber qué modelo produjo qué predicción, y cuál manda.

Sin esto, una predicción es un número sin procedencia. Con esto se puede responder la pregunta
que tarde o temprano hace alguien: «este pedido de hace tres semanas, ¿con qué modelo se
calculó, entrenado con qué datos, con qué código y con qué error de validación?».

El registro tiene **estados**, y ese es el cambio importante frente a una tabla de modelos a
secas. Entrenar ya no promueve:

    candidato  ──(puerta de promoción)──>  vigente  ──(entra otro)──>  retirado
        │
        └──(la puerta lo rechaza)────────> rechazado

Solo hay un modelo `vigente` por tipo, y es el único que predice. Un candidato se queda en el
disco con sus métricas anotadas aunque no pase: el histórico de lo que no se promovió es la
mitad de la información útil cuando algo va mal.

    python3 operacion/modelos.py                 # el registro completo
    python3 operacion/modelos.py --vigente       # solo el que está mandando
    python3 operacion/modelos.py --retroceder    # volver al anterior, ahora
"""
from __future__ import annotations
import argparse, os
import pandas as pd
from base import OPER, anexar, leer, ahora, nuevo_id, json_corto
import procedencia

CANDIDATO, VIGENTE, RETIRADO, RECHAZADO = "candidato", "vigente", "retirado", "rechazado"


def _guardar(df: pd.DataFrame) -> None:
    """Reescritura atómica del registro: temporal y reemplazo."""
    tmp = os.path.join(OPER, "dim_modelo.parquet.tmp")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, os.path.join(OPER, "dim_modelo.parquet"))


def registrar(tipo: str, hiperparametros: dict, ventana_dias: int,
              fecha_corte, metricas: dict, notas: str = "") -> str:
    """Da de alta un modelo recién entrenado **como candidato** y devuelve su identificador.

    Entrenar no promueve. Para que este modelo llegue a predecir tiene que pasar por
    `promocion.py`, que lo compara con el vigente y decide.
    """
    modelo_id = nuevo_id("mod")
    anexar("dim_modelo", [{
        "modelo_id": modelo_id,
        "momento_entrenamiento": ahora(),
        "tipo": tipo,
        "estado": CANDIDATO,
        "hiperparametros": json_corto(hiperparametros),
        "ventana_entrenamiento_dias": ventana_dias,
        "fecha_corte": str(fecha_corte),
        **procedencia.completa(),
        **{f"metrica_{k}": v for k, v in metricas.items()},
        "notas": notas,
        "momento_promocion": None,
        "motivo": "",
        # Se conserva por compatibilidad con lo ya escrito: `vigente` es booleano y `estado` es
        # la fuente de verdad. Quien lea una de las dos ve lo mismo.
        "vigente": False,
    }])
    return modelo_id


def promover(modelo_id: str, motivo: str = "") -> None:
    """Hace vigente a un candidato y retira al anterior de su mismo tipo."""
    df = leer("dim_modelo")
    if df.empty or modelo_id not in set(df["modelo_id"]):
        raise SystemExit(f"No existe el modelo {modelo_id} en el registro.")
    df = _asegurar_columnas(df)
    tipo = df.loc[df["modelo_id"] == modelo_id, "tipo"].iloc[0]

    anteriores = (df["tipo"] == tipo) & (df["estado"] == VIGENTE)
    df.loc[anteriores, ["estado", "vigente"]] = [RETIRADO, False]
    fila = df["modelo_id"] == modelo_id
    df.loc[fila, ["estado", "vigente"]] = [VIGENTE, True]
    df.loc[fila, "momento_promocion"] = ahora()
    df.loc[fila, "motivo"] = motivo[:500]
    _guardar(df)
    _escribir_puntero(modelo_id)


def rechazar(modelo_id: str, motivo: str) -> None:
    """Marca un candidato como rechazado. No se borra: el histórico de fallos es información."""
    df = _asegurar_columnas(leer("dim_modelo"))
    if df.empty:
        return
    fila = df["modelo_id"] == modelo_id
    df.loc[fila, ["estado", "vigente"]] = [RECHAZADO, False]
    df.loc[fila, "motivo"] = motivo[:500]
    _guardar(df)


def retroceder(tipo: str = "lightgbm_bloques") -> str:
    """Vuelve al modelo vigente anterior. Es el botón que se aprieta a las tres de la mañana.

    Deshacer tiene que ser más barato que diagnosticar. Aquí cuesta un comando y no reentrena
    nada: los pesos del modelo anterior siguen en disco, solo cambia a quién apunta el puntero.
    """
    df = _asegurar_columnas(leer("dim_modelo"))
    if df.empty:
        raise SystemExit("El registro está vacío: no hay a dónde volver.")
    del_tipo = df[df["tipo"] == tipo].sort_values("momento_entrenamiento")
    retirados = del_tipo[del_tipo["estado"] == RETIRADO]
    if retirados.empty:
        raise SystemExit(
            f"No hay ningún modelo retirado de tipo «{tipo}»: el vigente es el primero que hubo.\n"
            f"Retroceder no es la salida aquí; lo que corresponde es reentrenar o parar el sistema.")
    anterior = retirados["modelo_id"].iloc[-1]
    actual = vigente(tipo)
    promover(anterior, motivo=f"retroceso manual desde {actual['modelo_id'] if actual else '?'}")
    if actual is not None:
        df = _asegurar_columnas(leer("dim_modelo"))
        df.loc[df["modelo_id"] == actual["modelo_id"], "motivo"] = "retirado por retroceso manual"
        _guardar(df)
    return anterior


def vigente(tipo: str = "lightgbm_bloques") -> dict | None:
    df = _asegurar_columnas(leer("dim_modelo"))
    if df.empty:
        return None
    f = df[(df["tipo"] == tipo) & (df["estado"] == VIGENTE)]
    return f.iloc[-1].to_dict() if len(f) else None


def candidato(tipo: str = "lightgbm_bloques") -> dict | None:
    """El último candidato sin resolver de ese tipo: el que la puerta tiene que juzgar."""
    df = _asegurar_columnas(leer("dim_modelo"))
    if df.empty:
        return None
    f = df[(df["tipo"] == tipo) & (df["estado"] == CANDIDATO)].sort_values("momento_entrenamiento")
    return f.iloc[-1].to_dict() if len(f) else None


def historial(tipo: str | None = None) -> pd.DataFrame:
    df = _asegurar_columnas(leer("dim_modelo"))
    if df.empty or tipo is None:
        return df
    return df[df["tipo"] == tipo]


def _asegurar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    """Compatibilidad con registros escritos antes de que existieran los estados.

    Un registro viejo tiene `vigente` y no tiene `estado`. Se traduce al vuelo en vez de pedirle
    a nadie que borre su histórico: lo que era vigente sigue siendo vigente, y lo que no, pasa a
    retirado.
    """
    if df.empty:
        return df
    if "estado" not in df.columns:
        df = df.copy()
        df["estado"] = df.get("vigente", False).map({True: VIGENTE, False: RETIRADO})
    for col in ("momento_promocion", "motivo", "sha_git", "huella_datos", "huella_entorno",
                "rama_git"):
        if col not in df.columns:
            df[col] = None
    return df


def _escribir_puntero(modelo_id: str) -> None:
    """`vigente.txt` es lo que lee `predecir.py`. El registro manda; el fichero lo refleja."""
    directorio = os.path.join(OPER, "modelos")
    os.makedirs(directorio, exist_ok=True)
    with open(os.path.join(directorio, "vigente.txt"), "w") as f:
        f.write(modelo_id)


def _imprimir(df: pd.DataFrame) -> None:
    cols = [c for c in ["modelo_id", "momento_entrenamiento", "tipo", "estado", "fecha_corte",
                        "sha_git", "huella_datos"] if c in df]
    met = [c for c in df.columns if c.startswith("metrica_")]
    print(df[cols + met].to_string(index=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Registro de modelos de DSMarket")
    ap.add_argument("--vigente", action="store_true", help="mostrar solo el modelo vigente")
    ap.add_argument("--retroceder", action="store_true", help="volver al modelo vigente anterior")
    ap.add_argument("--tipo", default="lightgbm_bloques")
    a = ap.parse_args()

    if a.retroceder:
        anterior = retroceder(a.tipo)
        print(f"Vigente ahora: {anterior}")
        print("Las predicciones siguen siendo las del modelo retirado hasta que vuelvas a correr:")
        print("    python3 operacion/orquestador.py --desde predecir")
    elif a.vigente:
        v = vigente(a.tipo)
        if v is None:
            print("No hay ningún modelo vigente.")
        else:
            for k in ("modelo_id", "momento_entrenamiento", "fecha_corte", "sha_git",
                      "huella_datos", "huella_entorno", "momento_promocion", "motivo"):
                if v.get(k) is not None:
                    print(f"  {k:<24} {v[k]}")
            for k, val in v.items():
                if k.startswith("metrica_"):
                    print(f"  {k:<24} {val:.4f}")
    else:
        df = historial(None)
        if df.empty:
            print("No hay modelos registrados todavía.")
        else:
            _imprimir(df)
