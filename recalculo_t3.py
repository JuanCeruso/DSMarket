# -*- coding: utf-8 -*-
"""
Recalculo por pasos de la sección 6 del notebook 03 con el grupo de producto actual (6 grupos).
Cada ejecución trabaja unos 130 s, guarda el progreso en cache_forecast/rec6/ y sale; se repite hasta 'COMPLETO'.
Unidad de trabajo: (ventana, modo, bloque) con LightGBM y XGBoost. Al terminar escribe pred_fold*.pkl (modelo único)
y pred2_fold*.pkl (bloques semanales), el formato que lee el notebook.
"""
import os, sys, gc, time, json, pickle
import numpy as np, pandas as pd, lightgbm as lgb, xgboost as xgb
import forecast_segmentacion as fs

T0 = time.time(); LIM = int(os.environ.get('LIM', 130))
D = f"{fs.CACHE}/rec6"; os.makedirs(D, exist_ok=True)
EXTRA = ['grupo_producto']; FEAT = fs.BASE + EXTRA; CAT = fs.CAT_BASE + EXTRA
PL = dict(fs.PARAMS_LGB, num_threads=4)
PX = dict(objective='reg:tweedie', tweedie_variance_power=1.1, eval_metric='rmse', eta=0.05, max_depth=8,
          subsample=0.8, colsample_bytree=0.8, tree_method='hist', max_bin=127, nthread=4, seed=42)
V, P, cs, cal, meta, folds = fs.cargar()


def tarea(f, modo, b):
    base = f"{D}/f{f}_{modo}{b}"
    if os.path.exists(base + '.npz'):
        return True
    start, end = folds[f]
    ml = 28 if modo == 'u' else 7 * (b + 1)
    dias = range(start, end) if modo == 'u' else range(start + 7 * b, min(start + 7 * (b + 1), end))
    est = json.load(open(base + '.json')) if os.path.exists(base + '.json') else \
        {'lgb': {'hechas': 0, 'scores': [], 'tramos': [], 'fin': False}, 'xgb': {'hechas': 0, 'scores': [], 'fin': False}}
    Xtr = fs.construir_matriz(range(start - fs.TRAIN_DAYS, start - 28), V, P, cs, cal, meta, EXTRA, ml)
    Xva = fs.construir_matriz(range(start - 28, start), V, P, cs, cal, meta, EXTRA, ml)
    Atr, ytr = fs.a_float32(Xtr, FEAT), Xtr['y'].to_numpy(np.float32)
    Ava, yva = fs.a_float32(Xva, FEAT), Xva['y'].to_numpy(np.float32)
    del Xtr, Xva; gc.collect()
    L = est['lgb']
    if not L['fin']:
        ini_tr = np.load(base + '_tr.npy') if L['hechas'] else None
        ini_va = np.load(base + '_va.npy') if L['hechas'] else None
        kw = dict(feature_name=FEAT, categorical_feature=CAT, params={'max_bin': 127, 'verbose': -1})
        d1 = lgb.Dataset(Atr, label=ytr, init_score=ini_tr, **kw)
        d2 = lgb.Dataset(Ava, label=yva, init_score=ini_va, reference=d1, feature_name=FEAT, categorical_feature=CAT)
        d1.construct(); d2.construct(); gc.collect()

        def control(env):
            L['scores'].append(float(env.evaluation_result_list[0][2])); L['hechas'] += 1
            mejor = int(np.argmin(L['scores'])) + 1
            if L['hechas'] - mejor >= 50 or L['hechas'] >= 800:
                L['fin'] = True; raise lgb.callback.EarlyStopException(env.iteration, env.evaluation_result_list)
            if time.time() - T0 > LIM:
                raise lgb.callback.EarlyStopException(env.iteration, env.evaluation_result_list)
        try:
            m = lgb.train(PL, d1, num_boost_round=800, valid_sets=[d2], callbacks=[control], keep_training_booster=True)
        except lgb.basic.LightGBMError:                    # fallo numérico al continuar un tramo: se reinicia la unidad
            import glob
            for g_ in glob.glob(base + '*'): os.remove(g_)
            print('reinicio de', base, flush=True); return False
        n_arb = m.current_iteration()
        arch = f"{base}_l{len(L['tramos'])}.txt"; m.save_model(arch, num_iteration=n_arb)
        L['tramos'].append([arch, n_arb, m.feature_importance('gain').tolist()])
        if not L['fin']:
            np.save(base + '_tr.npy', m._Booster__inner_predict(data_idx=0)); np.save(base + '_va.npy', m._Booster__inner_predict(data_idx=1))
        json.dump(est, open(base + '.json', 'w')); del m, d1, d2; gc.collect()
        if not L['fin']:
            return False
    X_ = est['xgb']
    if not X_['fin']:
        dtr = xgb.DMatrix(Atr, label=ytr, feature_names=FEAT, nthread=4)
        dva = xgb.DMatrix(Ava, label=yva, feature_names=FEAT, nthread=4)
        while True:
            if time.time() - T0 > LIM:
                json.dump(est, open(base + '.json', 'w')); return False
            ev = {}
            prev = base + '_x.json' if X_['hechas'] else None
            m = xgb.train(PX, dtr, num_boost_round=20, evals=[(dva, 'val')], evals_result=ev, xgb_model=prev, verbose_eval=False)
            m.save_model(base + '_x.json')
            X_['scores'] += list(ev['val']['rmse']); X_['hechas'] += 20
            mejor = int(np.argmin(X_['scores'])) + 1
            if X_['hechas'] - mejor >= 50 or X_['hechas'] >= 800:
                X_['fin'] = True; break
        json.dump(est, open(base + '.json', 'w'))
        del dtr, dva
    del Atr, Ava; gc.collect()
    # predicción de las dos familias
    Xte = fs.construir_matriz(dias, V, P, cs, cal, meta, EXTRA, ml)
    Ate = fs.a_float32(Xte, FEAT)
    mejor_l = int(np.argmin(L['scores'])) + 1; resto = mejor_l; raw = 0
    imp = np.zeros(len(FEAT))
    for arch, n_arb, g in L['tramos']:
        usar = min(n_arb, resto)
        if usar > 0:
            raw = raw + lgb.Booster(model_file=arch).predict(Ate, num_iteration=usar, raw_score=True)
        resto -= usar; imp += np.array(g)
    mx = xgb.Booster(); mx.load_model(base + '_x.json')
    mejor_x = int(np.argmin(X_['scores'])) + 1
    px = mx.predict(xgb.DMatrix(Ate, feature_names=FEAT, nthread=4), iteration_range=(0, mejor_x))
    Ml = np.zeros((V.shape[0], end - start), np.float32); Mx = Ml.copy()
    Ml[Xte['serie'], Xte['dia'] - start] = np.exp(raw); Mx[Xte['serie'], Xte['dia'] - start] = px
    np.savez(base + '.npz', ml=Ml, mx=Mx, imp=imp, mejor_l=mejor_l, mejor_x=mejor_x)
    print(f"ventana {f+1} {modo}{b}: LightGBM {mejor_l} árboles, XGBoost {mejor_x}", flush=True)
    return True


def ensamblar(f, modo):
    start, end = folds[f]
    bl = [0] if modo == 'u' else range(4)
    Ml = np.zeros((V.shape[0], end - start), np.float32); Mx = Ml.copy(); imps = []
    for b in bl:
        z = np.load(f"{D}/f{f}_{modo}{b}.npz")
        Ml += z['ml']; Mx += z['mx']; imps.append(pd.Series(z['imp'], index=FEAT))
    sin = np.isnan(P[:, start:end])
    res = {'pred_lgb': np.where(sin, 0, Ml), 'pred_xgb': np.where(sin, 0, Mx),
           'importancia_lgb': pd.concat(imps, axis=1).mean(axis=1).sort_values(ascending=False)}
    pickle.dump(res, open(f"{fs.CACHE}/pred{'' if modo == 'u' else '2'}_fold{f}.pkl", 'wb'))


def tarea_q(b):
    """Percentil 90 (objetivo cuantílico) de la última ventana, por bloques semanales; solo LightGBM, con tramos."""
    f = 2; base = f"{D}/q{f}_{b}"
    if os.path.exists(base + '.npz'):
        return True
    start, end = folds[f]; ml = 7 * (b + 1)
    dias = range(start + 7 * b, min(start + 7 * (b + 1), end))
    est = json.load(open(base + '.json')) if os.path.exists(base + '.json') else {'hechas': 0, 'scores': [], 'tramos': [], 'fin': False}
    Xtr = fs.construir_matriz(range(start - fs.TRAIN_DAYS, start - 28), V, P, cs, cal, meta, EXTRA, ml)
    Xva = fs.construir_matriz(range(start - 28, start), V, P, cs, cal, meta, EXTRA, ml)
    Atr, ytr = fs.a_float32(Xtr, FEAT), Xtr['y'].to_numpy(np.float32)
    Ava, yva = fs.a_float32(Xva, FEAT), Xva['y'].to_numpy(np.float32)
    del Xtr, Xva; gc.collect()
    pq = {k: v for k, v in PL.items() if k != 'tweedie_variance_power'}
    pq.update(objective='quantile', alpha=0.90, metric='quantile')
    ini_tr = np.load(base + '_tr.npy') if est['hechas'] else None
    ini_va = np.load(base + '_va.npy') if est['hechas'] else None
    kw = dict(feature_name=FEAT, categorical_feature=CAT, params={'max_bin': 127, 'verbose': -1})
    d1 = lgb.Dataset(Atr, label=ytr, init_score=ini_tr, **kw)
    d2 = lgb.Dataset(Ava, label=yva, init_score=ini_va, reference=d1, feature_name=FEAT, categorical_feature=CAT)
    d1.construct(); d2.construct(); del Atr, Ava; gc.collect()

    def control(env):
        est['scores'].append(float(env.evaluation_result_list[0][2])); est['hechas'] += 1
        mejor = int(np.argmin(est['scores'])) + 1
        if est['hechas'] - mejor >= 50 or est['hechas'] >= 800:
            est['fin'] = True; raise lgb.callback.EarlyStopException(env.iteration, env.evaluation_result_list)
        if time.time() - T0 > LIM:
            raise lgb.callback.EarlyStopException(env.iteration, env.evaluation_result_list)
    m = lgb.train(pq, d1, num_boost_round=800, valid_sets=[d2], callbacks=[control], keep_training_booster=True)
    n_arb = m.current_iteration(); arch = f"{base}_l{len(est['tramos'])}.txt"
    m.save_model(arch, num_iteration=n_arb); est['tramos'].append([arch, n_arb])
    if not est['fin']:
        np.save(base + '_tr.npy', m._Booster__inner_predict(data_idx=0)); np.save(base + '_va.npy', m._Booster__inner_predict(data_idx=1))
    json.dump(est, open(base + '.json', 'w')); del m, d1, d2; gc.collect()
    if not est['fin']:
        return False
    Xte = fs.construir_matriz(dias, V, P, cs, cal, meta, EXTRA, ml); Ate = fs.a_float32(Xte, FEAT)
    mejor = int(np.argmin(est['scores'])) + 1; resto = mejor; raw = 0
    for arch, n in est['tramos']:
        usar = min(n, resto)
        if usar > 0:
            raw = raw + lgb.Booster(model_file=arch).predict(Ate, num_iteration=usar, raw_score=True)
        resto -= usar
    M = np.zeros((V.shape[0], end - start), np.float32)
    M[Xte['serie'], Xte['dia'] - start] = np.maximum(raw, 0)
    np.savez(base + '.npz', m=M, mejor=mejor)
    print(f"p90 bloque {b+1}: {mejor} árboles", flush=True)
    return True


pendiente = False
for b in range(4) if os.environ.get('Q') else []:
    if not tarea_q(b):
        pendiente = True; break
if os.environ.get('Q') and not pendiente:
    M = sum(np.load(f"{D}/q2_{b}.npz")['m'] for b in range(4))
    s_, e_ = folds[2]
    np.save(f"{fs.CACHE}/p90_eval.npy", np.where(np.isnan(P[:, s_:e_]), 0, M))
    print('p90_eval.npy escrito', flush=True)
if os.environ.get('Q'):
    print('PENDIENTE' if pendiente else 'COMPLETO'); sys.exit(0)
for f in range(3):
    for modo, bl in [('s', range(4)), ('u', [0])]:
        for b in bl:
            if not tarea(f, modo, b):
                pendiente = True; break
        if pendiente: break
        ensamblar(f, modo)
    if pendiente: break
print('PENDIENTE' if pendiente else 'COMPLETO', f"{time.time()-T0:.0f}s", flush=True)
