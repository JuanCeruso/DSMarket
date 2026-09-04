# -*- coding: utf-8 -*-
"""
Experimento 3 — Arquitecturas neuronales de series temporales.

Qué se prueba: NHITS y Temporal Fusion Transformer (TFT), las dos arquitecturas modernas
más relevantes para este problema, contra el LightGBM que ya tenemos, sobre el mismo
subconjunto de series y la misma ventana de validación.

Por qué estas dos y no una LSTM genérica:
  · **NHITS** descompone la serie en varias resoluciones temporales. Es rápido, no necesita
    variables externas y es el sucesor directo de N-BEATS, que ganó la competición M4.
  · **TFT** admite variables conocidas de antemano (calendario, precio) y devuelve
    **cuantiles de forma nativa** — que es justo lo que necesita la política de reposición.
    Además su mecanismo de atención permite ver a qué le presta atención el modelo.

Expectativa honesta, que conviene tener antes de correrlo: en la competición M5 —que tiene
exactamente esta estructura de datos— las soluciones ganadoras fueron ensambles de árboles,
no redes neuronales. Es probable que LightGBM gane también acá. **Eso no invalida el
experimento: lo convierte en un resultado publicable.** Poder escribir «probamos las
arquitecturas neuronales de referencia y confirmamos el hallazgo de la literatura, con
nuestros propios datos» es más sólido que no haberlo probado.

Coste: sobre 1.000 series y 8 semanas de validación, entre 40 y 90 minutos en un Mac con
Apple Silicon (PyTorch usa la GPU integrada vía MPS). Con las 30.490 series completas
haría falta una GPU dedicada.

    pip install "neuralforecast>=1.7" torch
    python3 avanzado/03_deep_learning.py --series 1000
"""
import argparse, os, sys, time, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comun import (cargar_matrices, folds, construir_matriz, a_float32,
                   FEATURES, CATEGORICAS, SALIDA, conectar, mae, rmse)

HORIZONTE = 28
DIAS_ENTRENAMIENTO = 730          # las redes necesitan mas historia que los arboles


def preparar_panel(V, P, cal, meta, series, ini):
    """Formato largo que espera neuralforecast: unique_id, ds, y + variables de calendario."""
    filas = []
    fechas = cal["fecha"].to_numpy()
    for k in series:
        desde = max(ini - DIAS_ENTRENAMIENTO, 0)
        y = V[k, desde:ini + HORIZONTE].astype(np.float32)
        filas.append(pd.DataFrame({
            "unique_id": f"{meta['item'].iloc[k]}|{meta['store_code'].iloc[k]}",
            "ds": fechas[desde:ini + HORIZONTE],
            "y": y}))
    panel = pd.concat(filas, ignore_index=True)
    panel["ds"] = pd.to_datetime(panel["ds"])
    # variables conocidas de antemano: el calendario se sabe siempre
    panel["dia_semana"] = panel["ds"].dt.weekday.astype(np.float32)
    panel["mes"] = panel["ds"].dt.month.astype(np.float32)
    panel["finde"] = (panel["ds"].dt.weekday >= 5).astype(np.float32)
    return panel


def main(n_series, epocas):
    t0 = time.time()
    import torch
    acelerador = "mps" if torch.backends.mps.is_available() else (
        "gpu" if torch.cuda.is_available() else "cpu")
    print(f"PyTorch {torch.__version__} · acelerador: {acelerador}", flush=True)

    print("cargando el almacén…", flush=True)
    V, P, cs, cal, meta = cargar_matrices()
    n_dias = V.shape[1]
    ini, fin = folds(n_dias)[2]            # fold 3, el mismo que usa el resto del proyecto

    # subconjunto: las series de mayor facturación, que son las que pesan en el WRMSSE
    con = conectar()
    top = con.execute(f"""
        SELECT item, store_code FROM dim_serie
        ORDER BY facturacion_90d DESC LIMIT {n_series}
    """).df()
    con.close()
    clave = {(i, s): k for k, (i, s) in enumerate(zip(meta["item"], meta["store_code"]))}
    series = [clave[(i, s)] for i, s in zip(top["item"], top["store_code"]) if (i, s) in clave]
    print(f"  {len(series):,} series seleccionadas por facturación  [{time.time()-t0:.0f}s]", flush=True)

    panel = preparar_panel(V, P, cal, meta, series, ini)
    entrenamiento = panel[panel["ds"] < cal["fecha"].iloc[ini]]
    real = panel[panel["ds"] >= cal["fecha"].iloc[ini]][["unique_id", "ds", "y"]]
    print(f"  panel: {len(entrenamiento):,} filas de entrenamiento  [{time.time()-t0:.0f}s]\n", flush=True)

    from neuralforecast import NeuralForecast
    from neuralforecast.models import NHITS, TFT
    from neuralforecast.losses.pytorch import DistributionLoss

    modelos = [
        NHITS(h=HORIZONTE, input_size=8 * HORIZONTE, max_steps=epocas,
              scaler_type="robust", accelerator=acelerador, random_seed=42,
              loss=DistributionLoss(distribution="Poisson", level=[90])),
        TFT(h=HORIZONTE, input_size=4 * HORIZONTE, max_steps=epocas,
            scaler_type="robust", accelerator=acelerador, random_seed=42,
            futr_exog_list=["dia_semana", "mes", "finde"],
            loss=DistributionLoss(distribution="Poisson", level=[90])),
    ]

    nf = NeuralForecast(models=modelos, freq="D")
    print("entrenando…  (esto es lo que tarda)", flush=True)
    nf.fit(df=entrenamiento[["unique_id", "ds", "y", "dia_semana", "mes", "finde"]],
           val_size=HORIZONTE)
    print(f"  entrenamiento terminado [{time.time()-t0:.0f}s]", flush=True)

    futuro = panel[panel["ds"] >= cal["fecha"].iloc[ini]][
        ["unique_id", "ds", "dia_semana", "mes", "finde"]]
    pred = nf.predict(futr_df=futuro).reset_index()
    comparacion = real.merge(pred, on=["unique_id", "ds"], how="left").fillna(0)

    # ---------- referencia: LightGBM sobre las mismas series ----------
    print("\nentrenando la referencia LightGBM sobre el mismo subconjunto…", flush=True)
    import lightgbm as lgb
    conjunto = set(series)
    pred_lgb = np.zeros((V.shape[0], HORIZONTE), np.float32)
    for bloque in range(4):
        min_lag = 7 * (bloque + 1)
        Xtr = construir_matriz(range(ini - 180, ini - 28), V, P, cs, cal, meta, min_lag)
        Xtr = Xtr[Xtr["serie"].isin(conjunto)]
        Xva = construir_matriz(range(ini - 28, ini), V, P, cs, cal, meta, min_lag)
        Xva = Xva[Xva["serie"].isin(conjunto)]
        d1 = lgb.Dataset(a_float32(Xtr), label=Xtr["y"].to_numpy(np.float32),
                         feature_name=FEATURES, categorical_feature=CATEGORICAS)
        m = lgb.train(dict(objective="tweedie", tweedie_variance_power=1.1, metric="rmse",
                           learning_rate=0.05, num_leaves=96, min_data_in_leaf=100,
                           feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1,
                           num_threads=4, verbose=-1, seed=42, max_bin=127),
                      d1, num_boost_round=800,
                      valid_sets=[lgb.Dataset(a_float32(Xva), label=Xva["y"].to_numpy(np.float32),
                                              reference=d1)],
                      callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)])
        Xte = construir_matriz(range(ini + 7 * bloque, min(ini + 7 * (bloque + 1), fin)),
                               V, P, cs, cal, meta, min_lag)
        Xte = Xte[Xte["serie"].isin(conjunto)]
        pred_lgb[Xte["serie"].values, Xte["dia"].values - ini] = \
            m.predict(a_float32(Xte), num_iteration=m.best_iteration)
        del Xtr, Xva, Xte, m

    idx = {f"{meta['item'].iloc[k]}|{meta['store_code'].iloc[k]}": k for k in series}
    comparacion["fila"] = comparacion["unique_id"].map(idx)
    comparacion["dia"] = (comparacion["ds"] - cal["fecha"].iloc[ini]).dt.days
    comparacion["LightGBM"] = pred_lgb[comparacion["fila"].to_numpy(),
                                       comparacion["dia"].to_numpy()]

    # ---------- resultados ----------
    columnas = {"NHITS": "NHITS", "TFT": "TFT", "LightGBM": "LightGBM (referencia)"}
    filas = []
    for col, nombre in columnas.items():
        if col not in comparacion:
            continue
        y, p = comparacion["y"].to_numpy(), comparacion[col].to_numpy()
        fila = {"modelo": nombre, "MAE": mae(y, p), "RMSE": rmse(y, p),
                "sesgo_%": float((p.sum() - y.sum()) / max(y.sum(), 1) * 100)}
        alto = f"{col}-hi-90"
        if alto in comparacion:
            fila["cobertura_p90"] = float((y <= comparacion[alto].to_numpy()).mean() * 100)
        filas.append(fila)

    resultado = pd.DataFrame(filas).set_index("modelo")
    print("\n=== NEURONALES vs ÁRBOLES · fold 3, mismas series ===")
    print(resultado.round(3).to_string())
    comparacion.to_csv(os.path.join(SALIDA, "deep_learning_predicciones.csv"), index=False)
    resultado.to_csv(os.path.join(SALIDA, "deep_learning_resumen.csv"))
    print(f"\nguardado en {SALIDA}  ·  total {time.time()-t0/60:.0f} min")
    print("\nCómo leerlo: si LightGBM gana, es un resultado válido y esperado — coincide con "
          "lo que ocurrió en la competición M5. Lo que sí conviene mirar aparte es la columna "
          "de cobertura: si el TFT calibra el intervalo mejor que nuestro modelo cuantílico, "
          "eso sí sería un argumento para usarlo en la parte de abastecimiento.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", type=int, default=1000,
                    help="cuántas series (por facturación). 1000 ≈ 40-90 min en Apple Silicon")
    ap.add_argument("--epocas", type=int, default=500, help="pasos de entrenamiento por modelo")
    a = ap.parse_args()
    main(a.series, a.epocas)
