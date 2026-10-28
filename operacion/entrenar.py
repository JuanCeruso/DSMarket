# -*- coding: utf-8 -*-
"""
Etapa de entrenamiento.

Entrena los ocho modelos que usa el sistema —cuatro bloques semanales por cada objetivo, media
y percentil 90—, los guarda en disco y **registra el modelo en `dim_modelo`** con sus
hiperparámetros y sus métricas de validación.

Guardar el modelo entrenado es lo que separa esta etapa de un cuaderno: la predicción de mañana
no vuelve a entrenar, carga lo que se entrenó hoy. Y el identificador que devuelve viaja con
cada predicción, de modo que dentro de tres semanas se puede saber qué modelo produjo un pedido
concreto.

**Entrenar ya no despliega.** Lo que sale de aquí es un *candidato*: queda registrado con sus
métricas, su SHA de git y la huella del almacén con el que se entrenó, pero no predice nada
hasta que `promocion.py` lo compare con el vigente y decida. Esa separación es lo que impide el
fallo más caro de todos, que es que un modelo peor sustituya en silencio al que funcionaba.

    python3 operacion/entrenar.py
    python3 operacion/entrenar.py --dias 180      # ventana corta (la versión anterior del modelo)
"""
from __future__ import annotations
import argparse, os, sys, time
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "avanzado"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comun import (cargar_matrices, construir_matriz, a_float32, FEATURES, CATEGORICAS,
                   HORIZONTE, mae, rmse)
from base import OPER
import modelos as reg
import procedencia
import lightgbm as lgb

DIRECTORIO = os.path.join(OPER, "modelos")
os.makedirs(DIRECTORIO, exist_ok=True)

COMUNES = dict(learning_rate=0.05, num_leaves=96, min_data_in_leaf=100, feature_fraction=0.8,
               bagging_fraction=0.8, bagging_freq=1, num_threads=4, verbose=-1, seed=42,
               max_bin=127)
OBJETIVOS = {
    "media": dict(COMUNES, objective="tweedie", tweedie_variance_power=1.1, metric="rmse"),
    "p90":   dict(COMUNES, objective="quantile", alpha=0.90, metric="quantile"),
}


def main(dias_entrenamiento, rondas):
    t0 = time.time()
    print("cargando el almacén…", flush=True)
    V, P, cs, cal, meta = cargar_matrices()
    n_dias = V.shape[1]
    corte = n_dias                      # se entrena con todo lo disponible
    validacion = (n_dias - 28, n_dias)  # las últimas 4 semanas, para las métricas del registro
    print(f"  {V.shape[0]:,} series x {n_dias:,} días  ·  corte {cal['fecha'].iloc[-1].date()}"
          f"  [{time.time()-t0:.0f}s]", flush=True)

    metricas = {}
    for objetivo, params in OBJETIVOS.items():
        print(f"\nobjetivo «{objetivo}»", flush=True)
        errores = []
        for bloque in range(4):
            min_lag = 7 * (bloque + 1)
            minimo = min_lag + 364          # la media móvil anual necesita ese histórico
            ini_tr = max(validacion[0] - dias_entrenamiento, minimo)
            if ini_tr >= validacion[0]:
                raise SystemExit(
                    f"Histórico insuficiente: hacen falta al menos {minimo + 28} días con venta "
                    f"y hay {n_dias}. La variable rmean_364 no tiene ventana.")
            Xtr = construir_matriz(range(ini_tr, validacion[0]), V, P, cs, cal, meta, min_lag)
            Xva = construir_matriz(range(*validacion), V, P, cs, cal, meta, min_lag)
            d1 = lgb.Dataset(a_float32(Xtr), label=Xtr["y"].to_numpy(np.float32),
                             feature_name=FEATURES, categorical_feature=CATEGORICAS)
            d2 = lgb.Dataset(a_float32(Xva), label=Xva["y"].to_numpy(np.float32), reference=d1)
            m = lgb.train(params, d1, num_boost_round=rondas, valid_sets=[d2],
                          callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)])
            pred = np.maximum(m.predict(a_float32(Xva), num_iteration=m.best_iteration), 0)
            y = Xva["y"].to_numpy(np.float32)
            errores.append(mae(y, pred) if objetivo == "media"
                           else float((y <= pred).mean()))
            m.save_model(os.path.join(DIRECTORIO, f"{objetivo}_bloque{bloque}.txt"),
                         num_iteration=m.best_iteration)
            print(f"  bloque {bloque} (retardo mínimo {min_lag:>2}d) · "
                  f"{'MAE' if objetivo=='media' else 'cobertura'} "
                  f"{errores[-1]:.4f} · {m.best_iteration} árboles  [{time.time()-t0:.0f}s]",
                  flush=True)
            del Xtr, Xva, d1, d2, m
        metricas["mae_validacion" if objetivo == "media" else "cobertura_p90"] = \
            float(np.mean(errores))

    modelo_id = reg.registrar(
        tipo="lightgbm_bloques",
        hiperparametros={"comunes": COMUNES, "objetivos": list(OBJETIVOS), "rondas": rondas},
        ventana_dias=dias_entrenamiento,
        fecha_corte=cal["fecha"].iloc[-1].date(),
        metricas=metricas,
        notas="4 bloques semanales por objetivo; validación en las últimas 4 semanas")

    print(f"\ncandidato registrado: {modelo_id}")
    for k, v in metricas.items():
        print(f"  {k}: {v:.4f}")
    print(f"  procedencia: {procedencia.sha_git()} · almacén {procedencia.huella_datos()}")
    print(f"pesos guardados en {DIRECTORIO}  ·  total {(time.time()-t0)/60:.1f} min")
    print("\nTodavía no predice nada. Para que llegue a producción tiene que pasar la puerta:")
    print("    python3 operacion/promocion.py")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dias", type=int, default=400,
                    help="ventana de entrenamiento (400 días: incluye el año anterior completo, Tarea 3 sección 9.2)")
    ap.add_argument("--rondas", type=int, default=800, help="número máximo de árboles")
    a = ap.parse_args()
    main(a.dias, a.rondas)
