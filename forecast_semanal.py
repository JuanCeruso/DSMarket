# -*- coding: utf-8 -*-
"""
Revisión de la Tarea 3 tras la tutoría: eventos a nivel semanal y medición del error por semanas.

Parte del modelo actualizado de la sección 15 (LightGBM por bloques semanales con la segmentación
actual de 6 grupos) y le añade cuatro variables de calendario que miran la SEMANA y no solo el día:

    sem_evento          1 si en la semana (sábado a viernes) hay algún evento
    evento_semana       qué evento hay esa semana (categórica; 0 = ninguno)
    dias_hasta_evento   días que faltan para el próximo evento (tope 15)
    dias_desde_evento   días desde el último evento (tope 8)

Todas se conocen de antemano por el calendario, así que no usan información del futuro.

Se evalúa en las 3 ventanas de validación (feb-abr 2016) y en las 2 de temporada alta
(nov y dic 2015), que es donde los eventos pesan de verdad.

Autocontenido: usa forecast_segmentacion.py y los CSV originales. Guarda los resultados en
cache_forecast/semanal_<config>_<ventana>.pkl.
"""
import os, gc, pickle, time
import numpy as np
import pandas as pd
import lightgbm as lgb
import forecast_segmentacion as fs

CACHE = fs.CACHE
EXTRA_SEMANAL = ['sem_evento', 'evento_semana', 'dias_hasta_evento', 'dias_desde_evento']
CONFIGS = {
    'actual': dict(extra=['grupo_producto'], semanal=False),
    'eventos_semanales': dict(extra=['grupo_producto'], semanal=True),
    # mismo modelo aprendiendo de 400 días en lugar de 180, para que vea al menos un ejemplo de cada evento
    'actual_400d': dict(extra=['grupo_producto'], semanal=False, train_days=400),
    'eventos_semanales_400d': dict(extra=['grupo_producto'], semanal=True, train_days=400),
}


def ventanas(cal, folds):
    """Las 3 ventanas de validación más las 2 de temporada alta de la sección 8."""
    idx = lambda f: int(cal.index[cal['date'] == pd.Timestamp(f)][0])
    v = {f'fold{i}': (s, e) for i, (s, e) in enumerate(folds)}
    v['nov2015'] = (idx('2015-11-06'), idx('2015-11-06') + 28)
    v['dic2015'] = (idx('2015-12-04'), idx('2015-12-04') + 28)
    return v


NOMBRE_VENTANA = {'fold0': 'Feb 2016', 'fold1': 'Mar 2016', 'fold2': 'Abr 2016',
                  'nov2015': 'Nov 2015 (Thanksgiving)', 'dic2015': 'Dic 2015 (Navidad)'}


def variables_semanales(cal):
    """Una fila por día con las 4 variables de evento semanal."""
    es_evento = cal['event_final'].notna().values
    n = len(cal)
    # semana sábado-viernes, como en el calendario original (sábado = día 1)
    semana = ((cal['date'] - pd.Timestamp('2011-01-29')).dt.days // 7).values
    ev_id = pd.factorize(cal['event_final'].fillna('none'))[0]
    df = pd.DataFrame({'semana': semana, 'es_evento': es_evento, 'ev_id': np.where(es_evento, ev_id, 0)})
    df['sem_evento'] = df.groupby('semana')['es_evento'].transform('max').astype(np.int8)
    df['evento_semana'] = df.groupby('semana')['ev_id'].transform('max').astype(np.int8)
    hasta = np.full(n, 15, np.int8); desde = np.full(n, 8, np.int8)
    pos = np.nonzero(es_evento)[0]
    for t in range(n):
        prox = pos[pos >= t]
        if len(prox): hasta[t] = min(prox[0] - t, 15)
        prev = pos[pos <= t]
        if len(prev): desde[t] = min(t - prev[-1], 8)
    df['dias_hasta_evento'] = hasta; df['dias_desde_evento'] = desde
    return df[EXTRA_SEMANAL]


def construir(dias, V, P, cs, cal, meta, extra, min_lag, sem):
    X = fs.construir_matriz(dias, V, P, cs, cal, meta, extra, min_lag)
    if sem is not None:
        X[EXTRA_SEMANAL] = sem.to_numpy()[X['dia'].values]
    return X


def entrenar(config, nombre, ventana, V, P, cs, cal, meta, sem):
    archivo = f"{CACHE}/semanal_{config}_{nombre}.pkl"
    if os.path.exists(archivo):
        return pickle.load(open(archivo, 'rb'))
    # las ventanas de validación de la configuración actual ya están entrenadas en la sección 15
    if config == 'actual' and nombre.startswith('fold'):
        folds = [v for k, v in ventanas(cal, fs_folds(V)).items() if k.startswith('fold')]
        r = fs.entrenar_fold('actual', int(nombre[-1]), V, P, cs, cal, meta, folds)
        pickle.dump(r, open(archivo, 'wb'))
        return r
    cfg = CONFIGS[config]
    extra = cfg['extra']
    s_sem = sem if cfg['semanal'] else None
    feats = fs.BASE + extra + (EXTRA_SEMANAL if cfg['semanal'] else [])
    cats = fs.CAT_BASE + extra + (['evento_semana'] if cfg['semanal'] else [])
    start, end = ventana
    train_days = cfg.get('train_days', fs.TRAIN_DAYS)
    M = np.zeros((V.shape[0], end - start), dtype=np.float32)
    imps = []
    params = dict(fs.PARAMS_LGB, num_threads=os.cpu_count())
    for b in range(4):
        min_lag = 7 * (b + 1)
        dias_pred = range(start + 7 * b, min(start + 7 * (b + 1), end))
        Xtr = construir(range(start - train_days, start - 28), V, P, cs, cal, meta, extra, min_lag, s_sem)
        Xva = construir(range(start - 28, start), V, P, cs, cal, meta, extra, min_lag, s_sem)
        Atr, ytr = fs.a_float32(Xtr, feats), Xtr['y'].to_numpy(np.float32)
        Ava, yva = fs.a_float32(Xva, feats), Xva['y'].to_numpy(np.float32)
        del Xtr, Xva; gc.collect()
        d1 = lgb.Dataset(Atr, label=ytr, feature_name=feats, categorical_feature=cats)
        m = lgb.train(params, d1, num_boost_round=800,
                      valid_sets=[lgb.Dataset(Ava, label=yva, reference=d1)],
                      callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)])
        imps.append(pd.Series(m.feature_importance('gain'), index=feats))
        del d1, Atr, ytr, Ava, yva; gc.collect()
        Xte = construir(dias_pred, V, P, cs, cal, meta, extra, min_lag, s_sem)
        M[Xte['serie'], Xte['dia'] - start] = m.predict(fs.a_float32(Xte, feats), num_iteration=m.best_iteration)
        del Xte, m; gc.collect()
    r = {'pred': np.where(np.isnan(P[:, start:end]), 0, M),
         'importancia': pd.concat(imps, axis=1).mean(axis=1).sort_values(ascending=False)}
    pickle.dump(r, open(archivo, 'wb'))
    return r


def fs_folds(V):
    n = V.shape[1]
    return [(n - fs.HORIZON * (fs.N_FOLDS - i), n - fs.HORIZON * (fs.N_FOLDS - i - 1)) for i in range(fs.N_FOLDS)]


# ------------------------------------------------------------------ métricas semanales
def a_semanas(M):
    """Suma cada bloque de 7 días: (series, 28 días) -> (series, 4 semanas)."""
    return M.reshape(M.shape[0], -1, 7).sum(axis=2)


def wape(y, yhat):
    """Error absoluto total dividido entre las unidades vendidas: 'me equivoco en un X % de lo que se vende'."""
    return float(np.abs(y - yhat).sum() / y.sum() * 100)


def media_movil_28(V, P, start, end):
    m = np.repeat(V[:, start - 28:start].mean(axis=1, keepdims=True), end - start, axis=1).astype(np.float32)
    return np.where(np.isnan(P[:, start:end]), 0, m)


if __name__ == '__main__':
    import sys
    solo = sys.argv[1:]          # p. ej. actual_400d eventos_semanales_400d
    orden = ['dic2015', 'nov2015', 'fold0', 'fold1', 'fold2']
    t0 = time.time()
    V, P, cs, cal, meta, folds = fs.cargar()
    sem = variables_semanales(cal)
    print(f"datos cargados en {time.time()-t0:.0f}s", flush=True)
    vs = ventanas(cal, folds)
    for nombre in (orden if solo else vs):
        v = vs[nombre]
        for config in (solo or CONFIGS):
            t = time.time()
            r = entrenar(config, nombre, v, V, P, cs, cal, meta, sem)
            s, e = v
            y = V[:, s:e].astype(np.float32)
            w = fs.wrmsse(y, r['pred'], V[:, :s].astype(np.float32), P[:, :s])
            print(f"{nombre} {config}: WRMSSE {w:.4f} | WAPE semanal {wape(a_semanas(y), a_semanas(r['pred'])):.1f}% "
                  f"({time.time()-t:.0f}s)", flush=True)
