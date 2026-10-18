# -*- coding: utf-8 -*-
"""Experimento de precios por pasos: cada ejecución trabaja ~140 s, guarda el progreso y sale.
Unidad de trabajo = (escenario, objetivo, bloque semanal). Se entrena una vez y se predice con dos matrices de precios.
    python3 exp_precios_paso.py  [objetivos separados por coma, por defecto media]
"""
import os, sys, gc, time, json
import numpy as np, lightgbm as lgb
import forecast_segmentacion as fs, forecast_semanal as fw, modelo_final as mf

T0 = time.time(); LIMITE = 135
D = f"{fs.CACHE}/exp3"; os.makedirs(D, exist_ok=True)
OBJ = (sys.argv[1] if len(sys.argv) > 1 else 'media').split(',')
CHUNK = 50

_ACT = {}


def escenario(esc):
    """Construye solo las matrices del escenario pedido (la memoria no alcanza para los dos a la vez)."""
    if _ACT.get('esc') == esc:
        return _ACT['c']
    _ACT.clear(); gc.collect()
    V, P, cs, cal, meta, folds = fs.cargar()
    if esc == 'sim':
        s, e = folds[2]
        Pc = P.copy(); Pc[:, s:e] = np.where(np.isnan(P[:, s:e]), np.nan, P[:, s - 1:s])
        c = dict(start=s, V=V, P=P, cs=cs, cal=cal, lista=[P, Pc])
    else:
        PF = fs.cargar_precios_futuros(meta)
        n = V.shape[1]
        V2, P2c, cs2, cal2 = mf.extender(V, P, cs, cal)
        _, P2r, _, _ = mf.extender(V, P, cs, cal, PF)
        del V, P, cs; gc.collect()
        c = dict(start=n, V=V2, P=P2c, cs=cs2, cal=cal2, lista=[P2r, P2c])
    c['sem'] = fw.variables_semanales(c['cal']); c['meta'] = meta
    _ACT.update(esc=esc, c=c)
    return c


def unidad(esc, obj, b):
    """Entrena por tramos entre ejecuciones: cada tramo continúa desde la puntuación acumulada (init_score)."""
    base = f"{D}/{esc}_{obj}_{b}"
    if os.path.exists(base + '.npz'):
        return True
    c = escenario(esc); start = c['start']; sem = c['sem']; meta = c['meta']; params = mf.OBJETIVOS[obj]
    ml = 7 * (b + 1)
    est = json.load(open(base + '.json')) if os.path.exists(base + '.json') else {'hechas': 0, 'scores': [], 'tramos': [], 'fin': False}
    if not est['fin']:
        Xtr = fw.construir(range(start - mf.TRAIN_DAYS, start - 28), c['V'], c['P'], c['cs'], c['cal'], meta, mf.EXTRA, ml, sem)
        Xva = fw.construir(range(start - 28, start), c['V'], c['P'], c['cs'], c['cal'], meta, mf.EXTRA, ml, sem)
        Atr, ytr = fs.a_float32(Xtr, mf.FEATURES), Xtr['y'].to_numpy(np.float32)
        Ava, yva = fs.a_float32(Xva, mf.FEATURES), Xva['y'].to_numpy(np.float32)
        del Xtr, Xva; gc.collect()
        ini_tr = np.load(base + '_tr.npy') if est['hechas'] else None
        ini_va = np.load(base + '_va.npy') if est['hechas'] else None
        kw = dict(feature_name=mf.FEATURES, categorical_feature=mf.CATEGORICAS, params={'max_bin': 127, 'verbose': -1})
        d1 = lgb.Dataset(Atr, label=ytr, init_score=ini_tr, **kw)
        d2 = lgb.Dataset(Ava, label=yva, init_score=ini_va, reference=d1, feature_name=mf.FEATURES, categorical_feature=mf.CATEGORICAS)
        d1.construct(); d2.construct(); del Atr, Ava; gc.collect()
        ev = {}

        def control(env):
            sc = env.evaluation_result_list[0][2]
            est['scores'].append(float(sc)); est['hechas'] += 1
            mejor = int(np.argmin(est['scores'])) + 1
            if est['hechas'] - mejor >= 50 or est['hechas'] >= 800:
                est['fin'] = True; raise lgb.callback.EarlyStopException(env.iteration, env.evaluation_result_list)
            if time.time() - T0 > LIMITE:
                raise lgb.callback.EarlyStopException(env.iteration, env.evaluation_result_list)
        tramo = len(est['tramos'])
        m = lgb.train(params, d1, num_boost_round=800, valid_sets=[d2], callbacks=[control], keep_training_booster=True)
        n_arb = m.current_iteration()
        archivo = f"{base}_t{tramo}.txt"
        m.save_model(archivo, num_iteration=n_arb)
        est['tramos'].append([archivo, n_arb])
        if not est['fin']:
            np.save(base + '_tr.npy', m._Booster__inner_predict(data_idx=0)); np.save(base + '_va.npy', m._Booster__inner_predict(data_idx=1))
        json.dump(est, open(base + '.json', 'w'))
        del m, d1, d2; gc.collect()
        if not est['fin']:
            return False
    mejor = int(np.argmin(est['scores'])) + 1
    resto = mejor; modelos = []
    for archivo, n_arb in est['tramos']:
        usar = min(n_arb, resto)
        if usar > 0:
            modelos.append((lgb.Booster(model_file=archivo), usar))
        resto -= usar
    out = {}
    for k, Pp in enumerate(c['lista']):
        Xte = fw.construir(range(start + 7 * b, start + 7 * (b + 1)), c['V'], Pp, c['cs'], c['cal'], meta, mf.EXTRA, ml, sem)
        A = fs.a_float32(Xte, mf.FEATURES)
        raw = sum(m.predict(A, num_iteration=u, raw_score=True) for m, u in modelos)
        pred = np.exp(raw) if obj == 'media' else raw
        M = np.zeros((c['V'].shape[0], 7), np.float32)
        M[Xte['serie'], Xte['dia'] - (start + 7 * b)] = np.maximum(pred, 0)
        out[f'p{k}'] = M; del Xte, A
    np.savez(base + '.npz', best=mejor, **out)
    print(f"{esc} {obj} bloque {b+1}: {mejor} árboles", flush=True)
    return True


def ensamblar(esc, obj):
    c = escenario(esc); start = c['start']
    for k, nombre in enumerate(['real', 'arrastrado']):
        M = np.zeros((c['V'].shape[0], fs.HORIZON), np.float32)
        for b in range(4):
            M[:, 7 * b:7 * (b + 1)] = np.load(f"{D}/{esc}_{obj}_{b}.npz")[f'p{k}']
        M = np.where(np.isnan(c['lista'][k][:, start:start + fs.HORIZON]), 0, M)
        np.save(f"{D}/{esc}_{obj}_{nombre}.npy", M)


pendiente = False
for obj in OBJ:
    for esc in (['ent'] if obj == 'p90' else ['sim', 'ent']):
        for b in range(4):
            if not unidad(esc, obj, b):
                pendiente = True; break
        else:
            if not os.path.exists(f"{D}/{esc}_{obj}_real.npy"):
                ensamblar(esc, obj)
            continue
        break
    if pendiente: break
print('PENDIENTE' if pendiente else 'COMPLETO', f"{time.time()-T0:.0f}s", flush=True)
