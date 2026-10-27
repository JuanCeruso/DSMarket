# -*- coding: utf-8 -*-
"""
Experimento 4 — Predicción conforme sobre el intervalo p90.

El problema que resuelve: nuestro modelo cuantílico dio una cobertura empírica del 90,0%
frente a un objetivo del 90%. Es un resultado excelente, pero es **empírico**: salió bien en
esa ventana, y nada garantiza que salga bien en la siguiente. La predicción conforme
(*conformalized quantile regression*, Romano et al.) convierte eso en una **garantía formal**:
bajo el supuesto de intercambiabilidad, la cobertura es de al menos 1−α en muestra finita,
sin asumir ninguna forma de la distribución.

Cómo funciona, en tres pasos:
  1. Se entrena el modelo cuantílico como siempre.
  2. Sobre un conjunto de **calibración que el modelo no vio**, se calcula para cada
     observación el error de conformidad  E = y − q̂90(x).
  3. Se toma el cuantil (1−α)(1+1/n) de esos errores y se suma al p90 predicho.

El resultado es un intervalo algo más ancho pero con cobertura garantizada. Para una política
de stock esa diferencia importa: un nivel de servicio prometido que no se cumple es peor que
uno más conservador que sí.

    python3 avanzado/04_conformal.py
"""
import os, sys, time
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comun import (cargar_matrices, folds, construir_matriz, a_float32,
                   FEATURES, CATEGORICAS, SALIDA, conectar)
import lightgbm as lgb

DIAS_ENTRENAMIENTO = 180
ALPHA = 0.10                       # objetivo de cobertura: 90%

PARAMS = dict(objective="quantile", alpha=1 - ALPHA, metric="quantile", learning_rate=0.05,
              num_leaves=96, min_data_in_leaf=100, feature_fraction=0.8,
              bagging_fraction=0.8, bagging_freq=1, num_threads=4, verbose=-1,
              seed=42, max_bin=127)


def entrenar_cuantil(ini, V, P, cs, cal, meta, dias_pred):
    """Modelo cuantilico por bloques semanales, igual que en la Tarea 3."""
    n_series = V.shape[0]
    salida = np.zeros((n_series, len(dias_pred)), np.float32)
    base = dias_pred[0]
    for bloque in range(4):
        min_lag = 7 * (bloque + 1)
        Xtr = construir_matriz(range(ini - DIAS_ENTRENAMIENTO, ini - 28), V, P, cs, cal, meta, min_lag)
        Xva = construir_matriz(range(ini - 28, ini), V, P, cs, cal, meta, min_lag)
        d1 = lgb.Dataset(a_float32(Xtr), label=Xtr["y"].to_numpy(np.float32),
                         feature_name=FEATURES, categorical_feature=CATEGORICAS)
        m = lgb.train(PARAMS, d1, num_boost_round=600,
                      valid_sets=[lgb.Dataset(a_float32(Xva), label=Xva["y"].to_numpy(np.float32),
                                              reference=d1)],
                      callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)])
        dias = [d for d in dias_pred if base + 7 * bloque <= d < base + 7 * (bloque + 1)]
        if dias:
            Xte = construir_matriz(dias, V, P, cs, cal, meta, min_lag)
            salida[Xte["serie"].values, Xte["dia"].values - base] = np.maximum(
                m.predict(a_float32(Xte), num_iteration=m.best_iteration), 0)
            del Xte
        del Xtr, Xva, m
    return salida


def main():
    t0 = time.time()
    print("cargando el almacén…", flush=True)
    V, P, cs, cal, meta = cargar_matrices()
    n_dias = V.shape[1]
    (ini_cal, fin_cal), (ini_test, fin_test) = folds(n_dias)[1], folds(n_dias)[2]

    print(f"calibración: fold 2 ({cal['fecha'].iloc[ini_cal].date()})", flush=True)
    q_cal = entrenar_cuantil(ini_cal, V, P, cs, cal, meta, list(range(ini_cal, fin_cal)))
    y_cal = V[:, ini_cal:fin_cal].astype(np.float32)
    valido_cal = ~np.isnan(P[:, ini_cal:fin_cal])

    # error de conformidad y su cuantil ajustado por tamaño de muestra
    errores = (y_cal - q_cal)[valido_cal]
    n = len(errores)
    nivel = min(np.ceil((n + 1) * (1 - ALPHA)) / n, 1.0)
    correccion = float(np.quantile(errores, nivel))
    print(f"  {n:,} observaciones de calibración · corrección conforme = {correccion:+.3f} unidades",
          flush=True)

    print(f"\nevaluación: fold 3 ({cal['fecha'].iloc[ini_test].date()})", flush=True)
    q_test = entrenar_cuantil(ini_test, V, P, cs, cal, meta, list(range(ini_test, fin_test)))
    y_test = V[:, ini_test:fin_test].astype(np.float32)
    valido = ~np.isnan(P[:, ini_test:fin_test])

    filas = []
    for nombre, pred in [("Cuantílico sin ajustar", q_test),
                         ("Conforme (garantía formal)", np.maximum(q_test + correccion, 0))]:
        y, p = y_test[valido], pred[valido]
        filas.append({"intervalo": nombre,
                      "cobertura_%": float((y <= p).mean() * 100),
                      "ancho_medio": float(p.mean()),
                      "unidades_totales": float(p.sum())})
    resultado = pd.DataFrame(filas).set_index("intervalo")
    print("\n=== COBERTURA DEL p90 EN EL FOLD 3 ===")
    print(resultado.round(3).to_string())

    # cobertura por segmento: donde importa que la garantía no se rompa
    con = conectar()
    serie_seg = con.execute("SELECT item, store_code, clase_abc, clase_xyz FROM dim_serie").df()
    con.close()
    clave = {(i, s): k for k, (i, s) in enumerate(zip(meta["item"], meta["store_code"]))}
    serie_seg["fila"] = [clave.get((i, s), -1) for i, s in
                         zip(serie_seg["item"], serie_seg["store_code"])]
    serie_seg = serie_seg[serie_seg["fila"] >= 0]

    print("\n=== COBERTURA POR CLASE XYZ ===")
    por_clase = []
    for clase in ["X", "Y", "Z"]:
        filas_c = serie_seg.loc[serie_seg["clase_xyz"] == clase, "fila"].to_numpy()
        v = valido[filas_c]
        por_clase.append({
            "clase": clase, "series": len(filas_c),
            "sin_ajustar_%": float((y_test[filas_c][v] <= q_test[filas_c][v]).mean() * 100),
            "conforme_%": float((y_test[filas_c][v] <=
                                 np.maximum(q_test[filas_c] + correccion, 0)[v]).mean() * 100)})
    print(pd.DataFrame(por_clase).round(2).to_string(index=False))

    resultado.to_csv(os.path.join(SALIDA, "conformal_resumen.csv"))
    pd.DataFrame(por_clase).to_csv(os.path.join(SALIDA, "conformal_por_clase.csv"), index=False)
    print(f"\nguardado en {SALIDA}  ·  total {time.time()-t0:.0f}s")
    print("\nCómo leerlo: si la corrección conforme es pequeña, significa que el modelo "
          "cuantílico ya estaba bien calibrado y lo único que ganamos es la garantía formal — "
          "que para la memoria es un argumento de rigor, no de rendimiento. Mira sobre todo la "
          "cobertura por clase: lo habitual es que la clase Z sea donde el modelo sin ajustar "
          "se queda corto, y es justo donde la garantía vale.")


if __name__ == "__main__":
    main()
