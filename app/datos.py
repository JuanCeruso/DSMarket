# -*- coding: utf-8 -*-
"""Acceso a datos de la app. Única puerta al lakehouse: la app no toca Parquet directamente."""
import os
import numpy as np, pandas as pd, duckdb
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLD = os.path.join(RAIZ, "lakehouse", "gold")

# La política vive en operacion/politica.py (una sola copia, compartida con la API y el almacén)
sys.path.insert(0, os.path.join(RAIZ, "operacion"))
import politica as pol
from historia import historia_reciente
PALETA = {"navy": "#0a2a5c", "azul": "#2a78d6", "dorado": "#eda100",
          "verde": "#6a9f1f", "gris": "#8a8a8a"}

def _leer(tabla: str) -> pd.DataFrame:
    con = duckdb.connect()
    df = con.execute(f"SELECT * FROM read_parquet('{os.path.join(GOLD, tabla)}.parquet')").df()
    con.close()
    return df

def cargar():
    """Devuelve las tablas que necesita la app. La app las cachea."""
    pred = _leer("fact_predicciones")
    pred["fecha"] = pd.to_datetime(pred["fecha"])
    series = _leer("dim_serie")
    series["celda"] = series["clase_abc"] + series["clase_xyz"]
    productos = _leer("dim_producto")
    tiendas = _leer("dim_tienda")
    return {"predicciones": pred, "series": series, "productos": productos, "tiendas": tiendas}

def historico(tienda: str, item: str, dias: int = 120) -> pd.DataFrame:
    con = duckdb.connect()
    df = con.execute(f"""
        SELECT fecha, unidades FROM read_parquet('{GOLD}/fact_ventas.parquet')
        WHERE store_code = ? AND item = ?
        ORDER BY fecha DESC LIMIT {dias}
    """, [tienda, item]).df()
    con.close()
    return df.sort_values("fecha")

_HIST = {}

def _historia():
    """Matriz de ventas recientes de todas las series (se lee una vez por proceso)."""
    if not _HIST:
        _HIST["datos"] = historia_reciente(GOLD, pol.VENTANA_HISTORIA)
    return _HIST["datos"]

def sugerir(pred_serie: pd.DataFrame, serie: pd.Series, stock: float, en_transito: float,
            dias_revision: int, lead_time: int, nivel_servicio: float | None):
    """Misma política que la API y el almacén (operacion/politica.py): híbrida por segmento."""
    cobertura = dias_revision + lead_time
    item, tienda = str(pred_serie["item"].iloc[0]), str(pred_serie["store_code"].iloc[0])
    servicio = nivel_servicio if nivel_servicio is not None else pol.nivel_servicio(item)
    bloque = pred_serie.head(cobertura)
    media_dia = pol.completar_ventana(bloque["prediccion_media"].to_numpy(), cobertura)
    p90_dia = pol.completar_ventana(bloque["prediccion_p90"].to_numpy(), cobertura)
    media = float(media_dia.sum())
    sigma = float(np.sqrt((pol.sigma_desde_cuantil(p90_dia, media_dia) ** 2).sum()))
    es_x = serie["clase_xyz"] == "X"
    fila_de, hist = _historia()
    empirico = float(pol.percentil_empirico(hist[fila_de[f"{item}|{tienda}"]], cobertura, servicio)[0])
    metodo = "percentil empírico (histórico)" if es_x else "modelo cuantílico"
    nivel = max(float(pol.nivel_hibrido(media, sigma, servicio, es_x, empirico)), 0.0)
    posicion = stock + en_transito
    return {"demanda_esperada": media, "nivel_objetivo": nivel,
            "stock_seguridad": max(nivel - media, 0.0), "posicion": posicion,
            "pedido": int(np.ceil(max(nivel - posicion, 0))), "servicio": servicio,
            "metodo": metodo, "cobertura": cobertura, "dias": bloque}

def explicacion_base(serie: pd.Series, resultado: dict, arquetipo: str) -> str:
    """Explicación por reglas. Es la que se usa si no hay LLM disponible."""
    celda = serie["celda"]
    valor = {"A": "alta facturación", "B": "facturación media", "C": "baja facturación"}[celda[0]]
    estab = {"X": "demanda estable", "Y": "demanda variable", "Z": "demanda errática"}[celda[1]]
    return (f"Segmento **{celda}** ({valor}, {estab}, CV {serie['coef_variacion']:.1f}), "
            f"grupo «{arquetipo}». Se cubren {resultado['cobertura']} días con un objetivo de "
            f"servicio del {resultado['servicio']:.0%}, calculado con {resultado['metodo']}. "
            f"La demanda esperada del período es {resultado['demanda_esperada']:.1f} unidades y el "
            f"stock de seguridad {resultado['stock_seguridad']:.1f}.")


# ---------------------------------------------------------------- vista de tienda
def pendientes(tienda: str, dias_revision: int, lead_time: int, nivel_servicio,
               cobertura_dias: float = 5.0, limite: int = 400) -> pd.DataFrame:
    """Las series de una tienda ordenadas por urgencia de pedido.

    El stock real no existe en el sistema, asi que se simula como `cobertura_dias` de venta
    media. En explotacion este es el punto exacto donde entra el dato del inventario: se
    sustituye esa linea y el resto de la funcion no cambia.
    """
    d = cargar()
    series = d["series"]
    series = series[series["store_code"] == tienda].copy()
    series = series.sort_values("facturacion_90d", ascending=False).head(limite)
    pred = d["predicciones"]
    pred = pred[pred["store_code"] == tienda]

    filas = []
    for _, s in series.iterrows():
        ps = pred[pred["item"] == s["item"]].sort_values("fecha")
        if ps.empty:
            continue
        stock = float(s["media_dia"]) * cobertura_dias        # <- sustituir por el stock real
        r = sugerir(ps, s, stock, 0.0, dias_revision, lead_time, nivel_servicio)
        deficit = r["nivel_objetivo"] - stock
        filas.append({
            "item": s["item"], "segmento": s["celda"],
            "stock_estimado": round(stock, 1),
            "demanda_ciclo": round(r["demanda_esperada"], 1),
            "nivel_objetivo": round(r["nivel_objetivo"], 1),
            "pedido_sugerido": r["pedido"],
            "servicio": r["servicio"],
            "urgencia": float(max(deficit, 0) * s["facturacion_90d"] / 90.0),
            "dias_de_cobertura": float(stock / max(s["media_dia"], 1e-6)),
        })
    df = pd.DataFrame(filas)
    if df.empty:
        return df
    df["excepcion"] = ""
    df.loc[df["dias_de_cobertura"] < 2, "excepcion"] = "riesgo de rotura"
    df.loc[df["pedido_sugerido"] == 0, "excepcion"] = "no hace falta pedir"
    df.loc[df["dias_de_cobertura"] > 30, "excepcion"] = "exceso de cobertura"
    return df.sort_values("urgencia", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------- registro de decisiones
DECISIONES = os.path.join(GOLD, "fact_decisiones.parquet")


def registrar_decisiones(filas: list) -> int:
    """Guarda lo que el encargado pidio realmente frente a lo sugerido.

    Escritura atomica mediante fichero temporal: si el proceso muere a mitad, el historico
    anterior sigue siendo legible.
    """
    import datetime as _dt
    if not filas:
        return 0
    nuevo = pd.DataFrame(filas)
    nuevo["momento"] = _dt.datetime.now().isoformat(timespec="seconds")
    if os.path.exists(DECISIONES):
        nuevo = pd.concat([pd.read_parquet(DECISIONES), nuevo], ignore_index=True)
    tmp = DECISIONES + ".tmp"
    nuevo.to_parquet(tmp, index=False)
    os.replace(tmp, DECISIONES)
    return len(nuevo)


def historico_decisiones() -> pd.DataFrame:
    return pd.read_parquet(DECISIONES) if os.path.exists(DECISIONES) else pd.DataFrame()
