# -*- coding: utf-8 -*-
"""
Modelo final de la Tarea 3 tras la revisión: LightGBM por bloques semanales, entrenado con
400 días de historia, con las variables de evento semanal y el grupo de producto actual.

Produce dos cosas, cada una con predicción media (objetivo tweedie) y percentil 90 (objetivo
cuantílico):

    cache_forecast/final_eval_media.npy, final_eval_p90.npy
        la última ventana de validación (28-mar a 24-abr de 2016), que usa el notebook 04
        para simular las políticas de reposición;
    cache_forecast/final_futuro_media.npy, final_futuro_p90.npy
        los 28 días siguientes al último día con datos (25-abr a 22-may de 2016): la entrega.

Precio de los días futuros, dos variantes:
    arrastrado       el último precio observado de cada serie (supuesto original, operacion/predecir.py);
    precios reales   los precios de las semanas posteriores que trae item_prices.csv sin yearweek
                     (EDA, sección 4.3); se activa con --precios-futuros y escribe archivos con sufijo _pf.

    python3 modelo_final.py                      # precio arrastrado
    python3 modelo_final.py --precios-futuros    # precios reales de las semanas futuras
"""
import os, gc, time
import numpy as np
import pandas as pd
import lightgbm as lgb
import forecast_segmentacion as fs
import forecast_semanal as fw

CACHE = fs.CACHE
TRAIN_DAYS = 400
EXTRA = ['grupo_producto']
FEATURES = fs.BASE + EXTRA + fw.EXTRA_SEMANAL
CATEGORICAS = fs.CAT_BASE + EXTRA + ['evento_semana']
_P90 = {k: v for k, v in fs.PARAMS_LGB.items() if k != 'tweedie_variance_power'}
OBJETIVOS = {
    'media': dict(fs.PARAMS_LGB, num_threads=os.cpu_count()),
    'p90': dict(_P90, objective='quantile', alpha=0.90, metric='quantile', num_threads=os.cpu_count()),
}


def extender(V, P, cs, cal, PF=None):
    """Añade 28 días futuros: ventas a cero (no se usan), precio (arrastrado o real) y calendario sin eventos.

    PF: precios de las semanas posteriores (series, semanas). Si es None, se arrastra el último precio.
    """
    H = fs.HORIZON
    ultimo = np.full(V.shape[0], np.nan, np.float32)
    for t in range(P.shape[1] - 1, max(P.shape[1] - 60, -1), -1):
        falta = np.isnan(ultimo)
        if not falta.any():
            break
        ultimo[falta] = P[falta, t]
    futuro = np.repeat(ultimo[:, None], H, axis=1)        # sin precio conocido: NaN, la serie queda fuera
    if PF is not None:
        n = P.shape[1]
        ultima_sem = (n - 1) // 7                          # semana a la que pertenece el último día con datos
        for j in range(H):
            k = (n + j) // 7 - ultima_sem                  # 0 = misma semana (precio ya conocido), 1.. = semanas posteriores
            if k >= 1:
                nuevo = PF[:, k - 1]
                futuro[:, j] = np.where(np.isnan(nuevo), futuro[:, j], nuevo)
    V2 = np.hstack([V, np.zeros((V.shape[0], H), V.dtype)])
    P2 = np.hstack([P, futuro])
    cs2 = np.zeros((V2.shape[0], V2.shape[1] + 1), np.float32)
    np.cumsum(V2, axis=1, dtype=np.float32, out=cs2[:, 1:])
    fechas = pd.date_range(cal['date'].max() + pd.Timedelta(days=1), periods=H)
    # en estas 4 semanas (25-abr a 22-may de 2016) no hay ningún evento del calendario
    cal2 = pd.concat([cal, pd.DataFrame({'date': fechas, 'event': np.nan, 'event_final': np.nan})],
                     ignore_index=True)
    return V2, P2, cs2, cal2


def entrenar_y_predecir(objetivo, start, V, P, cs, cal, meta, sem, P_pred=None):
    """4 bloques semanales: entrena con los 400 días previos a `start` y predice los 28 siguientes.

    P_pred: precios con los que se predice (por defecto, los mismos P). Permite probar precio arrastrado frente a real.
    """
    params = OBJETIVOS[objetivo]
    P_pred = P if P_pred is None else P_pred
    M = np.zeros((V.shape[0], fs.HORIZON), dtype=np.float32)
    for b in range(4):
        min_lag = 7 * (b + 1)
        Xtr = fw.construir(range(start - TRAIN_DAYS, start - 28), V, P, cs, cal, meta, EXTRA, min_lag, sem)
        Xva = fw.construir(range(start - 28, start), V, P, cs, cal, meta, EXTRA, min_lag, sem)
        Atr, ytr = fs.a_float32(Xtr, FEATURES), Xtr['y'].to_numpy(np.float32)
        Ava, yva = fs.a_float32(Xva, FEATURES), Xva['y'].to_numpy(np.float32)
        del Xtr, Xva; gc.collect()
        d1 = lgb.Dataset(Atr, label=ytr, feature_name=FEATURES, categorical_feature=CATEGORICAS)
        m = lgb.train(params, d1, num_boost_round=800,
                      valid_sets=[lgb.Dataset(Ava, label=yva, reference=d1)],
                      callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)])
        del d1, Atr, ytr, Ava, yva; gc.collect()
        Xte = fw.construir(range(start + 7 * b, start + 7 * (b + 1)), V, P_pred, cs, cal, meta, EXTRA, min_lag, sem)
        M[Xte['serie'], Xte['dia'] - start] = np.maximum(
            m.predict(fs.a_float32(Xte, FEATURES), num_iteration=m.best_iteration), 0)
        del Xte, m; gc.collect()
    return np.where(np.isnan(P_pred[:, start:start + fs.HORIZON]), 0, M)


def generar(nombre, start, V, P, cs, cal, meta, sufijo=''):
    sem = fw.variables_semanales(cal)
    salida = {}
    for objetivo in OBJETIVOS:
        archivo = f"{CACHE}/final_{nombre}_{objetivo}{sufijo}.npy"
        if os.path.exists(archivo):
            salida[objetivo] = np.load(archivo)
            continue
        t = time.time()
        salida[objetivo] = entrenar_y_predecir(objetivo, start, V, P, cs, cal, meta, sem)
        if objetivo == 'p90':                       # el p90 nunca por debajo de la media
            salida['p90'] = np.maximum(salida['p90'], salida['media'])
        np.save(archivo, salida[objetivo])
        print(f"{nombre} {objetivo}: {salida[objetivo].sum():,.0f} unidades ({time.time()-t:.0f}s)", flush=True)
    return salida


if __name__ == '__main__':
    import sys
    reales = '--precios-futuros' in sys.argv
    V, P, cs, cal, meta, folds = fs.cargar()
    if not reales:
        generar('eval', folds[2][0], V, P, cs, cal, meta)
    PF = fs.cargar_precios_futuros(meta) if reales else None
    V2, P2, cs2, cal2 = extender(V, P, cs, cal, PF)
    generar('futuro', V.shape[1], V2, P2, cs2, cal2, meta, sufijo='_pf' if reales else '')
