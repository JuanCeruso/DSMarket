# -*- coding: utf-8 -*-
"""
Recalculo por pasos de la sección de temporada alta del notebook 03 (eventos semanales y 400 días) con el grupo de producto
actual. Cada ejecución trabaja unos 160 s y guarda el progreso en cache_forecast/rec_sem/.
Escribe cache_forecast/semanal_{config}_{ventana}.pkl con el formato que lee forecast_semanal.entrenar().
"""
import os, sys, gc, time, json, pickle
import numpy as np, pandas as pd, lightgbm as lgb
import forecast_segmentacion as fs
import forecast_semanal as fw

T0 = time.time(); LIM = int(os.environ.get('LIM', 160))
D = f"{fs.CACHE}/rec_sem"; os.makedirs(D, exist_ok=True)
PL = dict(fs.PARAMS_LGB, num_threads=4)
V, P, cs, cal, meta, folds = fs.cargar()
sem = fw.variables_semanales(cal)
VENT = fw.ventanas(cal, folds)


def matriz(dias, ml, extra, s_sem, feats, trozo=20):
    """Construye la matriz float32 por trozos de días, para no tener a la vez el DataFrame completo y la matriz."""
    dias = list(dias)
    n = sum(int((~np.isnan(P[:, t])).sum()) for t in dias)
    A = np.empty((n, len(feats)), np.float32); y = np.empty(n, np.float32); pos = 0
    for i in range(0, len(dias), trozo):
        X = fw.construir(dias[i:i + trozo], V, P, cs, cal, meta, extra, ml, s_sem)
        A[pos:pos + len(X)] = fs.a_float32(X, feats); y[pos:pos + len(X)] = X['y'].to_numpy(np.float32)
        pos += len(X); del X
    gc.collect()
    return A, y


def tarea(config, nombre, b):
    base = f"{D}/{config}_{nombre}_{b}"
    if os.path.exists(base + '.npz'):
        return True
    cfg = fw.CONFIGS[config]
    extra = cfg['extra']; semanal = cfg['semanal']; dias_tr = cfg.get('train_days', fs.TRAIN_DAYS)
    feats = fs.BASE + extra + (fw.EXTRA_SEMANAL if semanal else [])
    cats = fs.CAT_BASE + extra + (['evento_semana'] if semanal else [])
    s_sem = sem if semanal else None
    start, end = VENT[nombre]; ml = 7 * (b + 1)
    dias = range(start + 7 * b, min(start + 7 * (b + 1), end))
    Atr, ytr = matriz(range(start - dias_tr, start - 28), ml, extra, s_sem, feats)
    Ava, yva = matriz(range(start - 28, start), ml, extra, s_sem, feats)
    pd_ = {'max_bin': 127, 'verbose': -1}
    d1 = lgb.Dataset(Atr, label=ytr, feature_name=feats, categorical_feature=cats, params=pd_)
    d2 = lgb.Dataset(Ava, label=yva, reference=d1, feature_name=feats, categorical_feature=cats)
    d1.construct(); d2.construct(); del Atr, Ava; gc.collect()
    m = lgb.train(PL, d1, num_boost_round=800, valid_sets=[d2],
                  callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)])
    imp = pd.Series(m.feature_importance('gain'), index=feats)
    del d1, d2; gc.collect()
    Xte = fw.construir(dias, V, P, cs, cal, meta, extra, ml, s_sem)
    M = np.zeros((V.shape[0], end - start), np.float32)
    M[Xte['serie'], Xte['dia'] - start] = m.predict(fs.a_float32(Xte, feats), num_iteration=m.best_iteration)
    np.savez(base + '.npz', M=M, imp=imp.values, names=np.array(feats), best=m.best_iteration)
    print(f"{config} {nombre} bloque {b+1}: {m.best_iteration} árboles ({time.time()-T0:.0f}s)", flush=True)
    return True


def ensamblar(config, nombre):
    archivo = f"{fs.CACHE}/semanal_{config}_{nombre}.pkl"
    start, end = VENT[nombre]
    M = np.zeros((V.shape[0], end - start), np.float32); imps = []
    for b in range(4):
        z = np.load(f"{D}/{config}_{nombre}_{b}.npz")
        M += z['M']; imps.append(pd.Series(z['imp'], index=list(z['names'])))
    r = {'pred': np.where(np.isnan(P[:, start:end]), 0, M),
         'importancia': pd.concat(imps, axis=1).mean(axis=1).sort_values(ascending=False)}
    pickle.dump(r, open(archivo, 'wb'))


# (config, ventana): 'actual' en feb-abr es el modelo de la sección 6; el resto se entrena aquí
PLAN = [('eventos_semanales', n) for n in ['fold2', 'dic2015', 'nov2015', 'fold0', 'fold1']] + \
       [('actual', n) for n in ['dic2015', 'nov2015']] + \
       [('actual_400d', n) for n in ['dic2015', 'nov2015', 'fold0', 'fold1', 'fold2']] + \
       [('eventos_semanales_400d', n) for n in ['dic2015', 'nov2015', 'fold0', 'fold1', 'fold2']]
pendiente = False
for config, nombre in PLAN:
    necesita = 68 if '400d' in config else 50
    for b in range(4):
        if os.path.exists(f"{D}/{config}_{nombre}_{b}.npz"):
            continue
        if time.time() - T0 > LIM - necesita:
            pendiente = True; break
        tarea(config, nombre, b)
    if pendiente: break
    if not os.path.exists(f"{fs.CACHE}/semanal_{config}_{nombre}.pkl"):
        ensamblar(config, nombre)
print('PENDIENTE' if pendiente else 'COMPLETO', f"{time.time()-T0:.0f}s", flush=True)
