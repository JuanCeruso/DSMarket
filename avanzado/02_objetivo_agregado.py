# -*- coding: utf-8 -*-
"""
Experimento 2 — Predecir el total del ciclo en vez de cada día por separado.

Esta es, de todos los experimentos, la que tiene más probabilidad de mover la aguja, y la
idea no es de modelado sino de encuadre del problema.

El razonamiento: la política de reposición no necesita saber cuánto se vende cada día.
Necesita **el total de los 9 días** que dura el ciclo de revisión más el plazo de entrega.
Hoy lo obtenemos sumando nueve predicciones diarias, y al sumarlas arrastramos nueve errores.
Un modelo entrenado directamente sobre el total del período tiene un objetivo menos ruidoso
—agregar promedia el ruido diario— y optimiza exactamente la cantidad que se usa.

También se prueba aquí el **ensamble** de LightGBM y XGBoost, que cuesta cinco líneas y en
problemas de este tipo suele aportar entre un 1% y un 2%.

    python3 avanzado/02_objetivo_agregado.py
"""
import os, sys, time, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comun import (cargar_matrices, folds, construir_matriz, a_float32,
                   FEATURES, CATEGORICAS, SALIDA, mae, rmse)
import lightgbm as lgb
import xgboost as xgb

DIAS_ENTRENAMIENTO = 180
R, L = 7, 2
COBERTURA = R + L

PARAMS_LGB = dict(objective="tweedie", tweedie_variance_power=1.1, metric="rmse",
                  learning_rate=0.05, num_leaves=96, min_data_in_leaf=100,
                  feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1,
                  num_threads=4, verbose=-1, seed=42, max_bin=127)
PARAMS_XGB = dict(objective="reg:tweedie", tweedie_variance_power=1.1, eval_metric="rmse",
                  eta=0.05, max_depth=8, subsample=0.8, colsample_bytree=0.8,
                  tree_method="hist", max_bin=127, nthread=4, seed=42)


def objetivo_agregado(V, dias, cobertura):
    """Para cada dia t, suma de unidades de los `cobertura` dias que empiezan en t."""
    n_dias = V.shape[1]
    cs = np.zeros((V.shape[0], n_dias + 1), np.float32)
    np.cumsum(V, axis=1, dtype=np.float32, out=cs[:, 1:])
    return {t: cs[:, min(t + cobertura, n_dias)] - cs[:, t] for t in dias}


def main():
    t0 = time.time()
    print("cargando el almacén…", flush=True)
    V, P, cs, cal, meta = cargar_matrices()
    n_series, n_dias = V.shape
    print(f"  {n_series:,} series × {n_dias:,} días  [{time.time()-t0:.0f}s]\n", flush=True)

    filas = []
    for fold, (ini, fin) in enumerate(folds(n_dias)):
        # solo evaluamos las fechas de revision reales: dia 0, 7, 14, 21 del horizonte
        revisiones = [ini + 7 * k for k in range(4) if ini + 7 * k + COBERTURA <= n_dias]
        if not revisiones:
            continue
        objetivo_real = objetivo_agregado(V, revisiones, COBERTURA)
        print(f"fold {fold+1}: {len(revisiones)} revisiones desde {cal['fecha'].iloc[ini].date()}",
              flush=True)

        # ---------- enfoque A: sumar predicciones diarias (el actual) ----------
        pred_diaria = np.zeros((n_series, fin - ini), np.float32)
        for bloque in range(4):
            min_lag = 7 * (bloque + 1)
            Xtr = construir_matriz(range(ini - DIAS_ENTRENAMIENTO, ini - 28), V, P, cs, cal, meta, min_lag)
            Xva = construir_matriz(range(ini - 28, ini), V, P, cs, cal, meta, min_lag)
            d1 = lgb.Dataset(a_float32(Xtr), label=Xtr["y"].to_numpy(np.float32),
                             feature_name=FEATURES, categorical_feature=CATEGORICAS)
            m = lgb.train(PARAMS_LGB, d1, num_boost_round=800,
                          valid_sets=[lgb.Dataset(a_float32(Xva), label=Xva["y"].to_numpy(np.float32),
                                                  reference=d1)],
                          callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)])
            dias_bloque = range(ini + 7 * bloque, min(ini + 7 * (bloque + 1), fin))
            Xte = construir_matriz(dias_bloque, V, P, cs, cal, meta, min_lag)
            pred_diaria[Xte["serie"].values, Xte["dia"].values - ini] = \
                m.predict(a_float32(Xte), num_iteration=m.best_iteration)
            del Xtr, Xva, Xte, m
        print(f"  enfoque diario listo [{time.time()-t0:.0f}s]", flush=True)

        # ---------- enfoque B: un modelo por el total del ciclo ----------
        dias_tr = [d for d in range(ini - DIAS_ENTRENAMIENTO, ini - 28) if d + COBERTURA <= ini]
        dias_va = [d for d in range(ini - 28, ini) if d + COBERTURA <= ini]
        obj_tr = objetivo_agregado(V, dias_tr, COBERTURA)
        obj_va = objetivo_agregado(V, dias_va, COBERTURA)

        Xtr = construir_matriz(dias_tr, V, P, cs, cal, meta, min_lag=1)
        Xva = construir_matriz(dias_va, V, P, cs, cal, meta, min_lag=1)
        ytr = np.array([obj_tr[d][s] for s, d in zip(Xtr["serie"], Xtr["dia"])], np.float32)
        yva = np.array([obj_va[d][s] for s, d in zip(Xva["serie"], Xva["dia"])], np.float32)
        Atr, Ava = a_float32(Xtr), a_float32(Xva)

        d1 = lgb.Dataset(Atr, label=ytr, feature_name=FEATURES, categorical_feature=CATEGORICAS)
        m_lgb = lgb.train(PARAMS_LGB, d1, num_boost_round=800,
                          valid_sets=[lgb.Dataset(Ava, label=yva, reference=d1)],
                          callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)])
        dtr = xgb.DMatrix(Atr, label=ytr, feature_names=FEATURES, nthread=4)
        dva = xgb.DMatrix(Ava, label=yva, feature_names=FEATURES, nthread=4)
        m_xgb = xgb.train(PARAMS_XGB, dtr, num_boost_round=800, evals=[(dva, "val")],
                          early_stopping_rounds=50, verbose_eval=False)
        del Xtr, Xva, Atr, Ava, dtr, dva
        print(f"  enfoque agregado listo [{time.time()-t0:.0f}s]", flush=True)

        # ---------- comparacion sobre las revisiones ----------
        for t in revisiones:
            Xte = construir_matriz([t], V, P, cs, cal, meta, min_lag=1)
            Ate = a_float32(Xte)
            ag_lgb = np.zeros(n_series, np.float32)
            ag_xgb = np.zeros(n_series, np.float32)
            ag_lgb[Xte["serie"].values] = m_lgb.predict(Ate, num_iteration=m_lgb.best_iteration)
            ag_xgb[Xte["serie"].values] = m_xgb.predict(
                xgb.DMatrix(Ate, feature_names=FEATURES, nthread=4),
                iteration_range=(0, m_xgb.best_iteration + 1))

            desde = t - ini
            suma_diaria = pred_diaria[:, desde:desde + COBERTURA].sum(axis=1)
            real = objetivo_real[t]
            activo = ~np.isnan(P[:, t])

            for nombre, pred in [("A · suma de predicciones diarias", suma_diaria),
                                 ("B · modelo del total (LightGBM)", ag_lgb),
                                 ("B · modelo del total (XGBoost)", ag_xgb),
                                 ("B · ensamble LGB+XGB", (ag_lgb + ag_xgb) / 2)]:
                filas.append({"fold": fold + 1, "revisión": str(cal["fecha"].iloc[t].date()),
                              "enfoque": nombre,
                              "MAE": mae(real[activo], pred[activo]),
                              "RMSE": rmse(real[activo], pred[activo]),
                              "sesgo_%": float((pred[activo].sum() - real[activo].sum())
                                               / max(real[activo].sum(), 1) * 100)})
            del Xte, Ate
        del pred_diaria, m_lgb, m_xgb

    res = pd.DataFrame(filas)
    resumen = res.groupby("enfoque")[["MAE", "RMSE", "sesgo_%"]].mean().sort_values("RMSE")
    print("\n=== PREDICCIÓN DEL TOTAL DE 9 DÍAS (promedio de todas las revisiones) ===")
    print(resumen.round(3).to_string())

    base = resumen.loc["A · suma de predicciones diarias", "RMSE"]
    print("\nmejora sobre el enfoque actual (RMSE):")
    for nombre, fila in resumen.iterrows():
        if nombre.startswith("B"):
            print(f"  {nombre:38s} {(base - fila['RMSE']) / base * 100:+6.2f}%")

    res.to_csv(os.path.join(SALIDA, "objetivo_agregado_detalle.csv"), index=False)
    resumen.to_csv(os.path.join(SALIDA, "objetivo_agregado_resumen.csv"))
    print(f"\nguardado en {SALIDA}  ·  total {time.time()-t0:.0f}s")
    print("\nCómo leerlo: si el enfoque B gana, la conclusión para la memoria es que el error "
          "no venía del modelo sino de cómo estaba planteado el objetivo — predecir la cantidad "
          "que realmente se usa en la decisión, en vez de predecir días sueltos y sumarlos.")


if __name__ == "__main__":
    main()
