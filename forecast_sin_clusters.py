# -*- coding: utf-8 -*-
"""
Variante del forecasting SIN la segmentación de producto (notebook 03b).

Reproduce exactamente el procedimiento de forecast_semanal.py y modelo_final.py (mismas ventanas,
mismos hiperparámetros, misma semilla, mismos bloques semanales) con una única diferencia:
la variable `grupo_producto` (los 6 grupos del clustering) NO se incluye entre las variables del modelo.
El resto de variables, incluido `item_id`, se mantiene.

Los resultados se guardan en cache_forecast_sin_clusters/ para no pisar los de la versión con clusters.

    python3 forecast_sin_clusters.py              # 2 configuraciones x 5 ventanas + modelo final
    python3 forecast_sin_clusters.py --completo   # las 4 configuraciones x 5 ventanas + modelo final
"""
import os, gc, pickle, time, sys
import numpy as np
import pandas as pd
import lightgbm as lgb
import forecast_segmentacion as fs
import forecast_semanal as fw
import modelo_final as mf

CACHE_SC = "cache_forecast_sin_clusters"
os.makedirs(CACHE_SC, exist_ok=True)

# misma definición que fw.CONFIGS, pero sin variables extra de segmentación
CONFIGS_SC = {
    'actual': dict(extra=[], semanal=False),
    'eventos_semanales': dict(extra=[], semanal=True),
    'actual_400d': dict(extra=[], semanal=False, train_days=400),
    'eventos_semanales_400d': dict(extra=[], semanal=True, train_days=400),
}


def entrenar(config, nombre, ventana, V, P, cs, cal, meta, sem):
    archivo = f"{CACHE_SC}/semanal_{config}_{nombre}.pkl"
    if os.path.exists(archivo):
        return pickle.load(open(archivo, 'rb'))
    cfg = CONFIGS_SC[config]
    extra = cfg['extra']
    s_sem = sem if cfg['semanal'] else None
    feats = fs.BASE + extra + (fw.EXTRA_SEMANAL if cfg['semanal'] else [])
    cats = fs.CAT_BASE + extra + (['evento_semana'] if cfg['semanal'] else [])
    start, end = ventana
    train_days = cfg.get('train_days', fs.TRAIN_DAYS)
    M = np.zeros((V.shape[0], end - start), dtype=np.float32)
    imps = []
    params = dict(fs.PARAMS_LGB, num_threads=os.cpu_count())
    for b in range(4):
        min_lag = 7 * (b + 1)
        dias_pred = range(start + 7 * b, min(start + 7 * (b + 1), end))
        Xtr = fw.construir(range(start - train_days, start - 28), V, P, cs, cal, meta, extra, min_lag, s_sem)
        Xva = fw.construir(range(start - 28, start), V, P, cs, cal, meta, extra, min_lag, s_sem)
        Atr, ytr = fs.a_float32(Xtr, feats), Xtr['y'].to_numpy(np.float32)
        Ava, yva = fs.a_float32(Xva, feats), Xva['y'].to_numpy(np.float32)
        del Xtr, Xva; gc.collect()
        d1 = lgb.Dataset(Atr, label=ytr, feature_name=feats, categorical_feature=cats)
        m = lgb.train(params, d1, num_boost_round=800,
                      valid_sets=[lgb.Dataset(Ava, label=yva, reference=d1)],
                      callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)])
        imps.append(pd.Series(m.feature_importance('gain'), index=feats))
        del d1, Atr, ytr, Ava, yva; gc.collect()
        Xte = fw.construir(dias_pred, V, P, cs, cal, meta, extra, min_lag, s_sem)
        M[Xte['serie'], Xte['dia'] - start] = m.predict(fs.a_float32(Xte, feats), num_iteration=m.best_iteration)
        del Xte, m; gc.collect()
    r = {'pred': np.where(np.isnan(P[:, start:end]), 0, M),
         'importancia': pd.concat(imps, axis=1).mean(axis=1).sort_values(ascending=False)}
    pickle.dump(r, open(archivo, 'wb'))
    return r


def modelo_final_sin_clusters(V, P, cs, cal, meta, folds):
    """Modelo final (400 días + eventos semanales, media y p90) sin grupo de producto, en la última ventana."""
    mf.EXTRA = []
    mf.FEATURES = fs.BASE + mf.EXTRA + fw.EXTRA_SEMANAL
    mf.CATEGORICAS = fs.CAT_BASE + mf.EXTRA + ['evento_semana']
    mf.CACHE = CACHE_SC
    return mf.generar('eval', folds[2][0], V, P, cs, cal, meta)


if __name__ == '__main__':
    completo = '--completo' in sys.argv
    t0 = time.time()
    V, P, cs, cal, meta, folds = fs.cargar()
    sem = fw.variables_semanales(cal)
    vs = fw.ventanas(cal, folds)
    configs = list(CONFIGS_SC) if completo else ['actual', 'eventos_semanales_400d']
    for nombre in ['fold2', 'dic2015', 'nov2015', 'fold0', 'fold1']:
        s, e = vs[nombre]
        y = V[:, s:e].astype(np.float32)
        for config in configs:
            t = time.time()
            r = entrenar(config, nombre, vs[nombre], V, P, cs, cal, meta, sem)
            w = fs.wrmsse(y, r['pred'], V[:, :s].astype(np.float32), P[:, :s])
            print(f"{nombre} {config}: WRMSSE {w:.4f} | WAPE semanal {fw.wape(fw.a_semanas(y), fw.a_semanas(r['pred'])):.1f}% "
                  f"({time.time()-t:.0f}s)", flush=True)
    modelo_final_sin_clusters(V, P, cs, cal, meta, folds)
    print(f"terminado en {(time.time()-t0)/60:.0f} min")
