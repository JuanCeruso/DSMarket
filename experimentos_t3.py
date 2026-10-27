# -*- coding: utf-8 -*-
"""
Experimentos de la revisión de la Tarea 3.

  complejidad   escalera de modelos, del más sencillo al modelo final, sobre las tres ventanas de validación.
  precios       precio arrastrado frente a precio real de las semanas posteriores (item_prices.csv sin yearweek):
                  - simulación en la última ventana de validación (28-mar a 24-abr de 2016): el mismo modelo
                    predice con el precio real de la ventana y con el último precio anterior arrastrado;
                  - entrega (25-abr a 22-may de 2016): predicción con precio arrastrado y con precio real.

    python3 experimentos_t3.py complejidad
    python3 experimentos_t3.py precios
"""
import os, sys, gc, time, pickle, json
import numpy as np, pandas as pd, lightgbm as lgb
import forecast_segmentacion as fs
import forecast_semanal as fw
import modelo_final as mf

CACHE = fs.CACHE


def metricas(y, yhat, V, P, s):
    return dict(wrmsse=fs.wrmsse(y, yhat, V[:, :s].astype(np.float32), P[:, :s]),
                wape_semanal=fw.wape(fw.a_semanas(y), fw.a_semanas(yhat)))


# ------------------------------------------------------------------ modelos sencillos
def ma28_por_dia_semana(V, P, cal, meta, s, e):
    """Media móvil de 28 días multiplicada por un factor de día de la semana por departamento (últimas 13 semanas)."""
    nivel = V[:, s - 28:s].mean(axis=1)
    wd = cal['date'].dt.weekday.values
    hist = V[:, s - 91:s].astype(np.float32)
    g = meta['dept_id'].to_numpy()
    f = np.ones((g.max() + 1, 7), np.float32)
    for k in range(g.max() + 1):
        filas = hist[g == k]
        total = filas.mean()
        for d in range(7):
            cols = wd[s - 91:s] == d
            f[k, d] = filas[:, cols].mean() / total if total > 0 else 1
    pred = np.zeros((V.shape[0], e - s), np.float32)
    for j, t in enumerate(range(s, e)):
        pred[:, j] = nivel * f[g, wd[t]]
    return np.where(np.isnan(P[:, s:e]), 0, pred)


SMALL_FEATS = ['lag_0', 'lag_1', 'rmean_7', 'rmean_28', 'weekday', 'is_weekend', 'sell_price']
SMALL_PARAMS = dict(objective='tweedie', tweedie_variance_power=1.1, learning_rate=0.1, num_leaves=15,
                    min_data_in_leaf=200, feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1,
                    num_threads=os.cpu_count(), verbose=-1, seed=42, max_bin=63)


def gbm_pequeno(V, P, cs, cal, meta, s, e):
    """LightGBM con 7 variables, 15 hojas y 300 árboles; 180 días de historia; 4 bloques semanales."""
    M = np.zeros((V.shape[0], e - s), np.float32)
    for b in range(4):
        ml = 7 * (b + 1)
        Xtr = fs.construir_matriz(range(s - 180, s - 28), V, P, cs, cal, meta, [], ml)
        A, y = fs.a_float32(Xtr, SMALL_FEATS), Xtr['y'].to_numpy(np.float32)
        del Xtr; gc.collect()
        m = lgb.train(SMALL_PARAMS, lgb.Dataset(A, label=y, feature_name=SMALL_FEATS,
                      categorical_feature=['weekday']), num_boost_round=300)
        del A, y; gc.collect()
        Xte = fs.construir_matriz(range(s + 7 * b, min(s + 7 * (b + 1), e)), V, P, cs, cal, meta, [], ml)
        M[Xte['serie'], Xte['dia'] - s] = np.maximum(m.predict(fs.a_float32(Xte, SMALL_FEATS)), 0)
        del Xte, m; gc.collect()
    return np.where(np.isnan(P[:, s:e]), 0, M)


def complejidad(solo=None):
    V, P, cs, cal, meta, folds = fs.cargar()
    arch = f"{CACHE}/exp_complejidad.csv"
    filas = pd.read_csv(arch).to_dict('records') if os.path.exists(arch) and solo is not None and solo > 0 else []
    for i, (s, e) in enumerate(folds):
        if solo is not None and i != solo:
            continue
        y = V[:, s:e].astype(np.float32)
        modelos = {}
        modelos['1 Media móvil 28 d'] = fw.media_movil_28(V, P, s, e)
        modelos['2 Media móvil × día de la semana'] = ma28_por_dia_semana(V, P, cal, meta, s, e)
        t = time.time(); modelos['3 LightGBM pequeño (7 variables, 15 hojas)'] = gbm_pequeno(V, P, cs, cal, meta, s, e)
        print(f"fold{i} GBM pequeño {time.time()-t:.0f}s", flush=True)
        modelos['4 LightGBM completo (96 hojas, 180 d)'] = pickle.load(open(f"{CACHE}/pred2_fold{i}.pkl", 'rb'))['pred_lgb']
        if i == 2:
            modelos['5 Modelo final (400 d + eventos semanales)'] = np.load(f"{CACHE}/final_eval_media.npy")
        for nom, pr in modelos.items():
            r = metricas(y, pr, V, P, s); r.update(ventana=f'fold{i}', modelo=nom); filas.append(r)
            print(f"fold{i} {nom}: WRMSSE {r['wrmsse']:.4f} WAPE sem {r['wape_semanal']:.1f}%", flush=True)
        pd.DataFrame(filas).to_csv(f"{CACHE}/exp_complejidad.csv", index=False)


# ------------------------------------------------------------------ precio arrastrado frente a real
def entrenar_doble(objetivo, start, V, P, cs, cal, meta, sem, lista_P):
    """Entrena una vez por bloque y predice con cada matriz de precios de `lista_P` (mismo modelo, distinto precio)."""
    params = mf.OBJETIVOS[objetivo]
    Ms = [np.zeros((V.shape[0], fs.HORIZON), np.float32) for _ in lista_P]
    for b in range(4):
        ml = 7 * (b + 1)
        Xtr = fw.construir(range(start - mf.TRAIN_DAYS, start - 28), V, P, cs, cal, meta, mf.EXTRA, ml, sem)
        Xva = fw.construir(range(start - 28, start), V, P, cs, cal, meta, mf.EXTRA, ml, sem)
        Atr, ytr = fs.a_float32(Xtr, mf.FEATURES), Xtr['y'].to_numpy(np.float32)
        Ava, yva = fs.a_float32(Xva, mf.FEATURES), Xva['y'].to_numpy(np.float32)
        del Xtr, Xva; gc.collect()
        d1 = lgb.Dataset(Atr, label=ytr, feature_name=mf.FEATURES, categorical_feature=mf.CATEGORICAS)
        m = lgb.train(params, d1, num_boost_round=800, valid_sets=[lgb.Dataset(Ava, label=yva, reference=d1)],
                      callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)])
        del d1, Atr, ytr, Ava, yva; gc.collect()
        for M, Pp in zip(Ms, lista_P):
            Xte = fw.construir(range(start + 7 * b, start + 7 * (b + 1)), V, Pp, cs, cal, meta, mf.EXTRA, ml, sem)
            M[Xte['serie'], Xte['dia'] - start] = np.maximum(
                m.predict(fs.a_float32(Xte, mf.FEATURES), num_iteration=m.best_iteration), 0)
            del Xte
        del m; gc.collect()
        print(f"  {objetivo} start={start} bloque {b+1}/4", flush=True)
    return [np.where(np.isnan(Pp[:, start:start + fs.HORIZON]), 0, M) for M, Pp in zip(Ms, lista_P)]


def precios():
    V, P, cs, cal, meta, folds = fs.cargar()
    sem = fw.variables_semanales(cal)
    s, e = folds[2]
    # simulación: precio arrastrado = último precio anterior a la ventana
    Pc = P.copy()
    ult = P[:, s - 1:s]
    Pc[:, s:e] = np.where(np.isnan(P[:, s:e]), np.nan, ult)
    cambia = (np.nan_to_num(P[:, s:e]) != np.nan_to_num(Pc[:, s:e])).any(axis=1)
    print(f"series con precio distinto al arrastrado en la ventana: {cambia.sum()} de {len(cambia)}", flush=True)
    y = V[:, s:e].astype(np.float32)
    sal = {}
    for obj in ['media', 'p90']:
        arch = f"{CACHE}/pf_sim_{obj}_real.npy"
        if os.path.exists(arch):
            sal[obj] = (np.load(arch), np.load(f"{CACHE}/pf_sim_{obj}_arrastrado.npy")); continue
        real, arr = entrenar_doble(obj, s, V, P, cs, cal, meta, sem, [P, Pc])
        np.save(arch, real); np.save(f"{CACHE}/pf_sim_{obj}_arrastrado.npy", arr); sal[obj] = (real, arr)
    for nom, pr in [('precio real', sal['media'][0]), ('precio arrastrado', sal['media'][1])]:
        r = metricas(y, pr, V, P, s); print(f"SIM {nom}: WRMSSE {r['wrmsse']:.4f} WAPE sem {r['wape_semanal']:.1f}%", flush=True)
    # entrega
    PF = fs.cargar_precios_futuros(meta)
    print("series con precio de semanas futuras:", int((~np.isnan(PF[:, 0])).sum()), flush=True)
    V2, P2c, cs2, cal2 = mf.extender(V, P, cs, cal)
    _, P2r, _, _ = mf.extender(V, P, cs, cal, PF)
    sem2 = fw.variables_semanales(cal2)
    n = V.shape[1]
    for obj in ['media', 'p90']:
        arch = f"{CACHE}/final_futuro_{obj}_pf.npy"
        if os.path.exists(arch): continue
        real, arr = entrenar_doble(obj, n, V2, P2c, cs2, cal2, meta, sem2, [P2r, P2c])
        np.save(arch, real); np.save(f"{CACHE}/pf_entrega_{obj}_arrastrado.npy", arr)
    print("fin", flush=True)


if __name__ == '__main__':
    if sys.argv[1] == 'complejidad':
        complejidad(int(sys.argv[2]) if len(sys.argv) > 2 else None)
    else:
        precios()
