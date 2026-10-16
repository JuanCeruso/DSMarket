# -*- coding: utf-8 -*-
"""
Utilidades compartidas por los experimentos avanzados.

Leen del lakehouse (`lakehouse/gold/`) y no de ficheros temporales, para que estos
scripts sigan funcionando aunque se borre cualquier caché.

Colocar esta carpeta como  PROYECTO/avanzado/  y ejecutar desde  PROYECTO/.
"""
from __future__ import annotations
import os, sys
import numpy as np
import pandas as pd
import duckdb

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLD = os.path.join(RAIZ, "lakehouse", "gold")
SALIDA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resultados")
os.makedirs(SALIDA, exist_ok=True)

HORIZONTE = 28
N_FOLDS = 3
LAGS = lambda min_lag: [min_lag, min_lag + 7, min_lag + 14, min_lag + 21, 364]
VENTANAS_MEDIA = [7, 28, 91, 364]

FEATURES = (["sell_price", "weekday", "month", "day_of_month", "week_of_year", "is_weekend", "event"]
            + [f"lag_{k}" for k in range(5)]
            + [f"rmean_{w}" for w in VENTANAS_MEDIA]
            + ["rstd_28", "zero_frac_28", "price_rel", "price_chg",
               "item_id", "store_id", "dept_id", "cat_id", "region_id", "grupo_producto",
               # eventos a nivel semanal (Tarea 3, sección 16)
               "sem_evento", "evento_semana", "dias_hasta_evento", "dias_desde_evento"])
CATEGORICAS = ["event", "item_id", "store_id", "dept_id", "cat_id", "region_id",
               "grupo_producto", "evento_semana", "weekday", "month"]
EXTRA_SEMANAL = ["sem_evento", "evento_semana", "dias_hasta_evento", "dias_desde_evento"]


def conectar():
    con = duckdb.connect()
    con.execute("SET memory_limit='6GB'; SET threads=4;")
    tmp = os.path.join(os.path.expanduser("~"), ".duckdb_tmp")
    os.makedirs(tmp, exist_ok=True)
    con.execute(f"SET temp_directory='{tmp}';")
    for f in sorted(os.listdir(GOLD)):
        if f.endswith(".parquet"):
            con.execute(f"CREATE OR REPLACE VIEW {f[:-8]} AS "
                        f"SELECT * FROM read_parquet('{os.path.join(GOLD, f)}')")
    return con


def cargar_matrices():
    """Reconstruye las matrices ancho (series x dias) que usan los modelos.

    Devuelve V (unidades, int16), P (precio, float32), cs (suma acumulada), cal, meta.
    Trabajar en formato ancho es lo que permite que esto entre en memoria: el formato
    largo son 58 millones de filas.
    """
    con = conectar()
    meta = con.execute("""
        SELECT s.item, s.store_code, p.categoria, p.departamento, p.grupo_producto,
               t.ciudad
        FROM dim_serie s
        JOIN dim_producto p USING (item)
        JOIN dim_tienda  t USING (store_code)
        ORDER BY s.item, s.store_code
    """).df()
    cal = con.execute("""
        SELECT fecha, dia_semana, weekday_int, anio, mes, semana_iso, evento,
               es_fin_de_semana, es_dia_cierre
        FROM dim_calendario WHERE NOT es_futuro ORDER BY fecha
    """).df()
    cal["fecha"] = pd.to_datetime(cal["fecha"])

    ancho = con.execute("""
        SELECT item, store_code, fecha, unidades, precio
        FROM fact_ventas ORDER BY item, store_code, fecha
    """)
    n_series, n_dias = len(meta), len(cal)
    V = np.zeros((n_series, n_dias), dtype=np.int16)
    P = np.full((n_series, n_dias), np.nan, dtype=np.float32)
    fila_de = {(i, s): k for k, (i, s) in enumerate(zip(meta["item"], meta["store_code"]))}
    col_de = {f: k for k, f in enumerate(cal["fecha"])}

    while True:                                   # por lotes: no cabe entero en memoria
        lote = ancho.fetch_df_chunk(200)
        if lote is None or len(lote) == 0:
            break
        filas = lote.apply(lambda r: fila_de[(r["item"], r["store_code"])], axis=1).to_numpy()
        cols = pd.to_datetime(lote["fecha"]).map(col_de).to_numpy()
        V[filas, cols] = lote["unidades"].to_numpy()
        P[filas, cols] = lote["precio"].astype(np.float32).to_numpy()
    con.close()

    cs = np.zeros((n_series, n_dias + 1), dtype=np.float32)
    np.cumsum(V, axis=1, dtype=np.float32, out=cs[:, 1:])

    for col, nuevo in [("item", "item_id"), ("store_code", "store_id"), ("departamento", "dept_id"),
                       ("categoria", "cat_id"), ("ciudad", "region_id")]:
        meta[nuevo] = pd.factorize(meta[col])[0].astype(np.int16)
    meta["grupo_producto"] = meta["grupo_producto"].astype(np.int16)
    return V, P, cs, cal, meta


def variables_semanales(cal):
    """Eventos vistos con perspectiva semanal: si la semana (sábado a viernes) tiene un evento,
    cuál, y cuántos días faltan para el próximo o han pasado desde el último. Se conocen de
    antemano por el calendario."""
    es_evento = cal["evento"].notna().to_numpy()
    n = len(cal)
    semana = ((pd.to_datetime(cal["fecha"]) - pd.Timestamp("2011-01-29")).dt.days // 7).to_numpy()
    ev_id = pd.factorize(cal["evento"].fillna("none"))[0]
    df = pd.DataFrame({"semana": semana, "es": es_evento, "ev": np.where(es_evento, ev_id, 0)})
    df["sem_evento"] = df.groupby("semana")["es"].transform("max").astype(np.int8)
    df["evento_semana"] = df.groupby("semana")["ev"].transform("max").astype(np.int8)
    pos = np.nonzero(es_evento)[0]
    hasta = np.full(n, 15, np.int8); desde = np.full(n, 8, np.int8)
    for t in range(n):
        prox = pos[pos >= t]
        if len(prox): hasta[t] = min(prox[0] - t, 15)
        prev = pos[pos <= t]
        if len(prev): desde[t] = min(t - prev[-1], 8)
    df["dias_hasta_evento"] = hasta; df["dias_desde_evento"] = desde
    return df[EXTRA_SEMANAL].to_numpy()


def folds(n_dias):
    """Tres ventanas consecutivas de 28 dias, la ultima termina en el ultimo dia con datos."""
    return [(n_dias - HORIZONTE * (N_FOLDS - i), n_dias - HORIZONTE * (N_FOLDS - i - 1))
            for i in range(N_FOLDS)]


def construir_matriz(dias, V, P, cs, cal, meta, min_lag=28):
    """Matriz de entrenamiento/prediccion. min_lag = antiguedad minima de la informacion usable."""
    lags = LAGS(min_lag)
    ev = pd.factorize(cal["evento"].fillna("none"))[0].astype(np.int8)
    wd = cal["fecha"].dt.weekday.values.astype(np.int8)
    mo = cal["fecha"].dt.month.values.astype(np.int8)
    dom = cal["fecha"].dt.day.values.astype(np.int8)
    woy = cal["fecha"].dt.isocalendar().week.values.astype(np.int8)
    bloques = []
    for t in dias:
        precio_t = P[:, t]
        idx = np.nonzero(~np.isnan(precio_t))[0]
        d = {"y": V[idx, t].astype(np.int16), "serie": idx.astype(np.int32),
             "dia": np.full(len(idx), t, np.int16), "sell_price": precio_t[idx],
             "weekday": np.full(len(idx), wd[t], np.int8), "month": np.full(len(idx), mo[t], np.int8),
             "day_of_month": np.full(len(idx), dom[t], np.int8),
             "week_of_year": np.full(len(idx), woy[t], np.int8),
             "is_weekend": np.full(len(idx), 1 if wd[t] >= 5 else 0, np.int8),
             "event": np.full(len(idx), ev[t], np.int8)}
        for k, L in enumerate(lags):
            d[f"lag_{k}"] = V[idx, t - L].astype(np.int16) if t - L >= 0 else np.zeros(len(idx), np.int16)
        for w in VENTANAS_MEDIA:
            a, b = max(t - min_lag - w, 0), max(t - min_lag, 0)
            d[f"rmean_{w}"] = ((cs[:, b] - cs[:, a]) / max(b - a, 1))[idx].astype(np.float32)
        a, b = max(t - min_lag - 28, 0), max(t - min_lag, 0)
        ventana = V[idx, a:b]
        d["rstd_28"] = ventana.std(axis=1).astype(np.float32)
        d["zero_frac_28"] = (ventana == 0).mean(axis=1).astype(np.float32)
        d["price_rel"] = (precio_t[idx] / np.nanmean(precio_t)).astype(np.float32)
        prev = P[:, max(t - 28, 0)][idx]
        d["price_chg"] = (precio_t[idx] /
                          np.where(np.isnan(prev) | (prev == 0), precio_t[idx], prev)).astype(np.float32)
        bloques.append(pd.DataFrame(d))
    X = pd.concat(bloques, ignore_index=True)
    del bloques
    cols = ["item_id", "store_id", "dept_id", "cat_id", "region_id", "grupo_producto"]
    X[cols] = meta[cols].to_numpy()[X["serie"].values]
    X[EXTRA_SEMANAL] = variables_semanales(cal)[X["dia"].values]
    return X


def a_float32(X):
    """LightGBM convierte un DataFrame a float64 internamente y agota la memoria: hay que
    pasarle un array float32 explicito."""
    A = np.empty((len(X), len(FEATURES)), dtype=np.float32)
    for j, c in enumerate(FEATURES):
        A[:, j] = X[c].to_numpy(dtype=np.float32)
    return A


# ------------------------------------------------------------------ metricas
def mae(y, yhat):  return float(np.mean(np.abs(y - yhat)))
def rmse(y, yhat): return float(np.sqrt(np.mean((y - yhat) ** 2)))

def rmsse_por_serie(y_true, y_pred, V_train):
    denom = np.mean(np.diff(V_train, axis=1) ** 2, axis=1)
    num = np.mean((y_true - y_pred) ** 2, axis=1)
    out = np.full(len(num), np.nan)
    m = denom > 0
    out[m] = np.sqrt(num[m] / denom[m])
    return out

def wrmsse(y_true, y_pred, V_train, P_train):
    r = rmsse_por_serie(y_true, y_pred, V_train)
    rev = (V_train[:, -28:] * np.nan_to_num(P_train[:, -28:])).sum(axis=1)
    w = rev / rev.sum()
    m = ~np.isnan(r)
    return float(np.sum(w[m] * r[m]) / np.sum(w[m]))
