# -*- coding: utf-8 -*-
"""
Reentrenamiento del modelo principal de la Tarea 3 (LightGBM por bloques semanales)
para comparar la segmentación anterior de la Tarea 2 con la actual.

Autocontenido: lee los CSV originales y no depende de resultados guardados por otras
celdas. Reproduce la lógica de 03_Forecasting_DSMarket.ipynb (secciones 2 a 6) y de
avanzado/comun.py.

    CONFIGURACIONES['anterior']  cluster_k5 + cluster_k10 + grupo de tienda (versión original)
    CONFIGURACIONES['actual']    grupo de producto de la nueva segmentación (6 grupos), sin grupo de tienda
"""
import os, gc, pickle, time
import numpy as np
import pandas as pd
import lightgbm as lgb

DATA_DIR = "data_dsmarket/data_dsmarket"
CACHE = "cache_forecast"
HORIZON, N_FOLDS, TRAIN_DAYS = 28, 3, 180
LAGS_BASE = lambda min_lag: [min_lag, min_lag + 7, min_lag + 14, min_lag + 21, 364]
RMEAN_WINDOWS = [7, 28, 91, 364]
PARAMS_LGB = dict(objective='tweedie', tweedie_variance_power=1.1, metric='rmse', learning_rate=0.05,
                  num_leaves=96, min_data_in_leaf=100, feature_fraction=0.8, bagging_fraction=0.8,
                  bagging_freq=1, num_threads=4, verbose=-1, seed=42, max_bin=127)

BASE = (['sell_price', 'weekday', 'month', 'day_of_month', 'week_of_year', 'is_weekend', 'event']
        + [f'lag_{k}' for k in range(5)] + [f'rmean_{W}' for W in RMEAN_WINDOWS]
        + ['rstd_28', 'zero_frac_28', 'price_rel', 'price_chg',
           'item_id', 'store_id', 'dept_id', 'cat_id', 'region_id'])
CAT_BASE = ['event', 'item_id', 'store_id', 'dept_id', 'cat_id', 'region_id', 'weekday', 'month']
CONFIGURACIONES = {
    'anterior': ['cluster_k5', 'cluster_k10', 'store_cluster'],
    'actual': ['grupo_producto'],
}


def cargar():
    """Matrices de ventas (V), precios (P), suma acumulada, calendario y metadatos de las 30.490 series."""
    calendar = pd.read_csv(f"{DATA_DIR}/daily_calendar_with_events.csv")
    calendar['date'] = pd.to_datetime(calendar['date'])
    sales = pd.read_csv(f"{DATA_DIR}/item_sales.csv")
    day_cols = [c for c in sales.columns if c.startswith('d_')]
    meta = sales[['id', 'item', 'category', 'department', 'store', 'store_code', 'region']].copy()
    V = sales[day_cols].to_numpy(dtype=np.int16)
    del sales; gc.collect()

    # precios: el fichero empieza 5 semanas antes que las ventas (sección 2 del notebook)
    prices = pd.read_csv(f"{DATA_DIR}/item_prices.csv").dropna(subset=['yearweek'])
    prices['yearweek'] = prices['yearweek'].astype(int)
    fila_de = pd.Series(np.arange(len(meta)), index=(meta['item'] + '|' + meta['store_code']).values)
    prices['row'] = (prices['item'] + '|' + prices['store_code']).map(fila_de).astype(np.int32)
    semanas = np.sort(prices['yearweek'].unique())
    n_series, n_days = V.shape
    n_weeks = int(np.ceil(n_days / 7))
    prices['widx'] = prices['yearweek'].map({w: i for i, w in enumerate(semanas)}) - (len(semanas) - n_weeks)
    pw = prices[prices['widx'] >= 0]
    P_week = np.full((n_series, n_weeks), np.nan, dtype=np.float32)
    P_week[pw['row'].values, pw['widx'].values] = pw['sell_price'].values.astype(np.float32)
    P = np.repeat(P_week, 7, axis=1)[:, :n_days]
    del P_week, prices, pw; gc.collect()

    cumsum = np.zeros((n_series, n_days + 1), dtype=np.float32)
    np.cumsum(V, axis=1, dtype=np.float32, out=cumsum[:, 1:])

    # eventos: los del calendario + Navidad y Labor Day añadidos por regla de fecha (EDA, sección 11)
    cal = calendar[['date', 'event']].copy()
    navidad = (cal['date'].dt.month == 12) & (cal['date'].dt.day == 25)
    labor = (cal['date'].dt.month == 9) & (cal['date'].dt.weekday == 0) & (cal['date'].dt.day <= 7)
    cal['event_final'] = cal['event']
    cal.loc[navidad, 'event_final'] = 'Christmas'
    cal.loc[labor, 'event_final'] = 'Labor Day'

    for col, nuevo in [('item', 'item_id'), ('store_code', 'store_id'), ('department', 'dept_id'),
                       ('category', 'cat_id'), ('region', 'region_id')]:
        meta[nuevo] = pd.factorize(meta[col])[0].astype(np.int16)

    # segmentación anterior (cluster_k5, cluster_k10 y grupos de tienda) y actual (6 grupos de producto)
    ant = pd.read_csv(f"{CACHE}/clusters_producto.csv", index_col=0)
    tie = pd.read_csv(f"{CACHE}/clusters_tienda.csv", index_col=0)
    act = pd.read_csv(f"{CACHE}/segmentacion_productos.csv", index_col=0)
    meta['cluster_k5'] = meta['item'].map(ant['cluster_k5']).astype(np.int8)
    meta['cluster_k10'] = meta['item'].map(ant['cluster_k10']).astype(np.int8)
    meta['store_cluster'] = meta['store_code'].map(tie['cluster_k3']).astype(np.int8)
    meta['grupo_producto'] = meta['item'].map(act['grupo']).astype(np.int8)
    meta['nombre_grupo'] = meta['item'].map(act['nombre_grupo'])
    folds = [(n_days - HORIZON * (N_FOLDS - i), n_days - HORIZON * (N_FOLDS - i - 1)) for i in range(N_FOLDS)]
    return V, P, cumsum, cal, meta, folds


def construir_matriz(dias, V, P, cumsum, cal, meta, extra, min_lag=28):
    lags = LAGS_BASE(min_lag)
    ev = pd.factorize(cal['event_final'].fillna('none'))[0].astype(np.int8)
    wd = cal['date'].dt.weekday.values.astype(np.int8)
    mo = cal['date'].dt.month.values.astype(np.int8)
    dom = cal['date'].dt.day.values.astype(np.int8)
    woy = cal['date'].dt.isocalendar().week.values.astype(np.int8)
    bloques = []
    for t in dias:
        precio_t = P[:, t]
        idx = np.nonzero(~np.isnan(precio_t))[0]
        d = {'y': V[idx, t].astype(np.int16), 'serie': idx.astype(np.int32),
             'dia': np.full(len(idx), t, dtype=np.int16), 'sell_price': precio_t[idx],
             'weekday': np.full(len(idx), wd[t], np.int8), 'month': np.full(len(idx), mo[t], np.int8),
             'day_of_month': np.full(len(idx), dom[t], np.int8),
             'week_of_year': np.full(len(idx), woy[t], np.int8),
             'is_weekend': np.full(len(idx), 1 if wd[t] >= 5 else 0, np.int8),
             'event': np.full(len(idx), ev[t], np.int8)}
        for k, L in enumerate(lags):
            d[f'lag_{k}'] = V[idx, t - L].astype(np.int16) if t - L >= 0 else np.zeros(len(idx), np.int16)
        for W in RMEAN_WINDOWS:
            a, b = max(t - min_lag - W, 0), max(t - min_lag, 0)
            d[f'rmean_{W}'] = ((cumsum[:, b] - cumsum[:, a]) / max(b - a, 1))[idx].astype(np.float32)
        a, b = max(t - min_lag - 28, 0), max(t - min_lag, 0)
        ventana = V[idx, a:b]
        d['rstd_28'] = ventana.std(axis=1).astype(np.float32)
        d['zero_frac_28'] = (ventana == 0).mean(axis=1).astype(np.float32)
        d['price_rel'] = (precio_t[idx] / np.nanmean(precio_t)).astype(np.float32)
        prev = P[:, max(t - 28, 0)][idx]
        d['price_chg'] = (precio_t[idx] / np.where(np.isnan(prev) | (prev == 0), precio_t[idx], prev)).astype(np.float32)
        bloques.append(pd.DataFrame(d))
    X = pd.concat(bloques, ignore_index=True); del bloques
    cols = ['item_id', 'store_id', 'dept_id', 'cat_id', 'region_id'] + extra
    X[cols] = meta[cols].to_numpy()[X['serie'].values]
    return X


def a_float32(X, features):
    A = np.empty((len(X), len(features)), dtype=np.float32)
    for j, c in enumerate(features):
        A[:, j] = X[c].to_numpy(dtype=np.float32)
    return A


def entrenar_fold(config, fold, V, P, cumsum, cal, meta, folds):
    """LightGBM por bloques semanales (4 modelos) para un fold. Guarda el resultado en caché."""
    archivo = f"{CACHE}/actualizacion_{config}_fold{fold}.pkl"
    if os.path.exists(archivo):
        return pickle.load(open(archivo, 'rb'))
    extra = CONFIGURACIONES[config]
    features, categoricas = BASE + extra, CAT_BASE + extra
    start, end = folds[fold]
    M = np.zeros((V.shape[0], end - start), dtype=np.float32)
    imps = []
    for b in range(4):
        min_lag = 7 * (b + 1)
        dias_pred = range(start + 7 * b, min(start + 7 * (b + 1), end))
        Xtr = construir_matriz(range(start - TRAIN_DAYS, start - 28), V, P, cumsum, cal, meta, extra, min_lag)
        Xva = construir_matriz(range(start - 28, start), V, P, cumsum, cal, meta, extra, min_lag)
        Atr, ytr = a_float32(Xtr, features), Xtr['y'].to_numpy(np.float32)
        Ava, yva = a_float32(Xva, features), Xva['y'].to_numpy(np.float32)
        del Xtr, Xva; gc.collect()
        d1 = lgb.Dataset(Atr, label=ytr, feature_name=features, categorical_feature=categoricas)
        m = lgb.train(PARAMS_LGB, d1, num_boost_round=800,
                      valid_sets=[lgb.Dataset(Ava, label=yva, reference=d1)],
                      callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)])
        imps.append(pd.Series(m.feature_importance('gain'), index=features))
        del d1, Atr, ytr, Ava, yva; gc.collect()
        Xte = construir_matriz(dias_pred, V, P, cumsum, cal, meta, extra, min_lag)
        M[Xte['serie'], Xte['dia'] - start] = m.predict(a_float32(Xte, features), num_iteration=m.best_iteration)
        del Xte, m; gc.collect()
    res = {'pred': np.where(np.isnan(P[:, start:end]), 0, M),
           'importancia': pd.concat(imps, axis=1).mean(axis=1).sort_values(ascending=False)}
    pickle.dump(res, open(archivo, 'wb'))
    return res


# ------------------------------------------------------------------ métricas (iguales que en el notebook)
def mae(y, yhat):
    return float(np.mean(np.abs(y - yhat)))


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


if __name__ == '__main__':
    t0 = time.time()
    V, P, cumsum, cal, meta, folds = cargar()
    print(f"datos cargados en {time.time()-t0:.0f}s", flush=True)
    for config in ['actual', 'anterior']:
        for f in range(N_FOLDS):
            t = time.time()
            r = entrenar_fold(config, f, V, P, cumsum, cal, meta, folds)
            s, e = folds[f]
            w = wrmsse(V[:, s:e].astype(np.float32), r['pred'], V[:, :s].astype(np.float32), P[:, :s])
            print(f"{config} fold {f+1}: WRMSSE {w:.4f} ({time.time()-t:.0f}s)", flush=True)
