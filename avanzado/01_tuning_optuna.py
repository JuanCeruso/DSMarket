# -*- coding: utf-8 -*-
"""
Experimento 1 — Búsqueda de hiperparámetros con Optuna.

Qué hace: busca la mejor combinación de hiperparámetros de LightGBM optimizando el WRMSSE
sobre el fold 2, y valida el resultado en el fold 3 (que no participó de la búsqueda).

Por qué así: optimizar y evaluar en el mismo fold sería hacer trampa — el modelo quedaría
ajustado a ese período concreto. Separar el fold de búsqueda del de validación es lo que
hace que la mejora reportada sea creíble.

Expectativa honesta: entre 1% y 2% de mejora en WRMSSE. El diagnóstico de la Tarea 3
—que `rmean_28` concentra el 71,7% de la importancia— indica que el techo lo pone el ruido
de la serie, no la configuración del modelo. Vale la pena hacerlo igual, porque en la
defensa es razonable que pregunten si se ajustaron los hiperparámetros.

    pip install optuna lightgbm
    python3 avanzado/01_tuning_optuna.py --pruebas 40
"""
import argparse, json, os, sys, time
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comun import (cargar_matrices, folds, construir_matriz, a_float32,
                   FEATURES, CATEGORICAS, SALIDA, wrmsse, mae)
import lightgbm as lgb
import optuna

optuna.logging.set_verbosity(optuna.logging.WARNING)
DIAS_ENTRENAMIENTO = 180


def datos_del_fold(fold, V, P, cs, cal, meta, min_lag=7):
    inicio, fin = folds(V.shape[1])[fold]
    Xtr = construir_matriz(range(inicio - DIAS_ENTRENAMIENTO, inicio - 28), V, P, cs, cal, meta, min_lag)
    Xva = construir_matriz(range(inicio - 28, inicio), V, P, cs, cal, meta, min_lag)
    Xte = construir_matriz(range(inicio, fin), V, P, cs, cal, meta, min_lag)
    return (a_float32(Xtr), Xtr["y"].to_numpy(np.float32),
            a_float32(Xva), Xva["y"].to_numpy(np.float32),
            a_float32(Xte), Xte, inicio, fin)


def main(n_pruebas):
    t0 = time.time()
    print("cargando el almacén…", flush=True)
    V, P, cs, cal, meta = cargar_matrices()
    n_series = V.shape[0]
    print(f"  {V.shape[0]:,} series × {V.shape[1]:,} días  [{time.time()-t0:.0f}s]", flush=True)

    # bloque de la primera semana del horizonte: es el que más pesa y el más rápido de iterar
    Atr, ytr, Ava, yva, Ate, Xte, ini, fin = datos_del_fold(1, V, P, cs, cal, meta)
    y_real = V[:, ini:fin].astype(np.float32)
    hist = V[:, :ini].astype(np.float32)
    P_hist = P[:, :ini]
    sin_precio = np.isnan(P[:, ini:fin])

    def evaluar(modelo):
        pred = modelo.predict(Ate, num_iteration=modelo.best_iteration)
        M = np.zeros((n_series, fin - ini), np.float32)
        M[Xte["serie"].values, Xte["dia"].values - ini] = pred
        return wrmsse(y_real, np.where(sin_precio, 0, M), hist, P_hist)

    def objetivo(prueba):
        params = dict(
            objective="tweedie",
            tweedie_variance_power=prueba.suggest_float("tweedie_variance_power", 1.0, 1.9),
            learning_rate=prueba.suggest_float("learning_rate", 0.02, 0.12, log=True),
            num_leaves=prueba.suggest_int("num_leaves", 32, 384, log=True),
            min_data_in_leaf=prueba.suggest_int("min_data_in_leaf", 20, 600, log=True),
            feature_fraction=prueba.suggest_float("feature_fraction", 0.5, 1.0),
            bagging_fraction=prueba.suggest_float("bagging_fraction", 0.5, 1.0),
            bagging_freq=1,
            lambda_l2=prueba.suggest_float("lambda_l2", 1e-3, 20.0, log=True),
            metric="rmse", num_threads=4, verbose=-1, seed=42, max_bin=127)
        d1 = lgb.Dataset(Atr, label=ytr, feature_name=FEATURES, categorical_feature=CATEGORICAS)
        modelo = lgb.train(params, d1, num_boost_round=1500,
                           valid_sets=[lgb.Dataset(Ava, label=yva, reference=d1)],
                           callbacks=[lgb.early_stopping(60, verbose=False), lgb.log_evaluation(0)])
        prueba.set_user_attr("arboles", modelo.best_iteration)
        return evaluar(modelo)

    print(f"\nbuscando sobre el fold 2 · {n_pruebas} pruebas", flush=True)
    estudio = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=42))
    estudio.optimize(objetivo, n_trials=n_pruebas, show_progress_bar=False,
                     callbacks=[lambda e, p: print(
                         f"  prueba {p.number+1:>3}/{n_pruebas}  WRMSSE {p.value:.4f}"
                         f"   mejor {e.best_value:.4f}   [{time.time()-t0:.0f}s]", flush=True)])

    print(f"\nmejor configuración (WRMSSE {estudio.best_value:.4f} en el fold de búsqueda):")
    for k, v in estudio.best_params.items():
        print(f"  {k:26s} {v}")

    # --------- validación limpia en el fold 3, que no participó de la búsqueda ---------
    print("\nvalidando en el fold 3 (no usado en la búsqueda)…", flush=True)
    base = dict(objective="tweedie", tweedie_variance_power=1.1, learning_rate=0.05,
                num_leaves=96, min_data_in_leaf=100, feature_fraction=0.8,
                bagging_fraction=0.8, bagging_freq=1, metric="rmse",
                num_threads=4, verbose=-1, seed=42, max_bin=127)
    afinado = dict(base, **estudio.best_params, metric="rmse")

    Atr3, ytr3, Ava3, yva3, Ate3, Xte3, ini3, fin3 = datos_del_fold(2, V, P, cs, cal, meta)
    y3 = V[:, ini3:fin3].astype(np.float32)
    hist3, Ph3 = V[:, :ini3].astype(np.float32), P[:, :ini3]
    sin_precio3 = np.isnan(P[:, ini3:fin3])

    filas = []
    for nombre, params in [("Configuración original", base), ("Configuración afinada", afinado)]:
        d1 = lgb.Dataset(Atr3, label=ytr3, feature_name=FEATURES, categorical_feature=CATEGORICAS)
        m = lgb.train(params, d1, num_boost_round=1500,
                      valid_sets=[lgb.Dataset(Ava3, label=yva3, reference=d1)],
                      callbacks=[lgb.early_stopping(60, verbose=False), lgb.log_evaluation(0)])
        pred = m.predict(Ate3, num_iteration=m.best_iteration)
        M = np.zeros((n_series, fin3 - ini3), np.float32)
        M[Xte3["serie"].values, Xte3["dia"].values - ini3] = pred
        M = np.where(sin_precio3, 0, M)
        filas.append({"configuración": nombre, "árboles": m.best_iteration,
                      "WRMSSE": wrmsse(y3, M, hist3, Ph3), "MAE": mae(y3, M)})

    resultado = pd.DataFrame(filas).set_index("configuración")
    print("\n=== RESULTADO EN EL FOLD 3 ===")
    print(resultado.round(4).to_string())
    mejora = (resultado.loc["Configuración original", "WRMSSE"] -
              resultado.loc["Configuración afinada", "WRMSSE"]) / resultado.loc["Configuración original", "WRMSSE"] * 100
    print(f"\nmejora del afinado: {mejora:+.2f}%")
    print("Si la mejora es menor al 1%, la conclusión honesta para la memoria es que el modelo "
          "ya estaba en una zona plana: el margen no está en los hiperparámetros.")

    json.dump({"mejores_parametros": estudio.best_params,
               "wrmsse_busqueda": estudio.best_value,
               "validacion_fold3": resultado.reset_index().to_dict("records"),
               "mejora_pct": mejora},
              open(os.path.join(SALIDA, "tuning_optuna.json"), "w"), indent=2, ensure_ascii=False)
    estudio.trials_dataframe().to_csv(os.path.join(SALIDA, "tuning_pruebas.csv"), index=False)
    print(f"\nguardado en {SALIDA}  ·  total {time.time()-t0:.0f}s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pruebas", type=int, default=40,
                    help="número de configuraciones a probar (40 ≈ 40-60 min)")
    main(ap.parse_args().pruebas)
