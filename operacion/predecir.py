# -*- coding: utf-8 -*-
"""
Etapa de predicción.

Carga los modelos entrenados —no reentrena— y produce las predicciones de los 28 días
siguientes al último día con venta, escribiendo `fact_predicciones` con el identificador del
modelo que las generó.

El precio de los días futuros no se conoce: se arrastra el último precio observado de cada
serie. Es un supuesto, y como tal se declara: si la compañía planifica un cambio de precio, ese
precio debería entrar aquí y no arrastrarse.

    python3 operacion/predecir.py
"""
from __future__ import annotations
import os, sys, time
import numpy as np, pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "avanzado"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comun import cargar_matrices, construir_matriz, a_float32, HORIZONTE
from base import GOLD, OPER, conectar
import lightgbm as lgb

DIRECTORIO = os.path.join(OPER, "modelos")


def extender(V, P, cs, cal):
    """Añade los 28 días futuros: ventas a cero (no se usan) y precio arrastrado."""
    con = conectar()
    fut = con.execute("""SELECT fecha, dia_semana, weekday_int, anio, mes, semana_iso, evento,
                                es_fin_de_semana, es_dia_cierre
                         FROM dim_calendario WHERE es_futuro ORDER BY fecha LIMIT 28""").df()
    con.close()
    if len(fut) < HORIZONTE:
        raise SystemExit(f"dim_calendario solo tiene {len(fut)} días futuros; hacen falta {HORIZONTE}. "
                         f"Extendé la dimensión temporal antes de predecir.")
    fut["fecha"] = pd.to_datetime(fut["fecha"])
    cal2 = pd.concat([cal, fut], ignore_index=True)

    ultimo = np.full(V.shape[0], np.nan, np.float32)
    for t in range(P.shape[1] - 1, max(P.shape[1] - 60, -1), -1):
        falta = np.isnan(ultimo)
        if not falta.any():
            break
        ultimo[falta] = P[falta, t]
    ultimo = np.nan_to_num(ultimo, nan=0.0)

    V2 = np.hstack([V, np.zeros((V.shape[0], HORIZONTE), V.dtype)])
    futuro = np.repeat(ultimo[:, None], HORIZONTE, axis=1)
    futuro[ultimo == 0, :] = np.nan          # sin precio conocido: la serie queda fuera
    P2 = np.hstack([P, futuro])
    cs2 = np.zeros((V2.shape[0], V2.shape[1] + 1), np.float32)
    np.cumsum(V2, axis=1, dtype=np.float32, out=cs2[:, 1:])
    return V2, P2, cs2, cal2


def main():
    t0 = time.time()
    vig = os.path.join(DIRECTORIO, "vigente.txt")
    if not os.path.exists(vig):
        raise SystemExit("No hay modelo entrenado. Ejecutá primero: python3 operacion/entrenar.py")
    modelo_id = open(vig).read().strip()
    print(f"modelo vigente: {modelo_id}", flush=True)

    V, P, cs, cal, meta = cargar_matrices()
    n_real = V.shape[1]
    V, P, cs, cal = extender(V, P, cs, cal)
    print(f"  horizonte: {cal['fecha'].iloc[n_real].date()} … {cal['fecha'].iloc[-1].date()}"
          f"  [{time.time()-t0:.0f}s]", flush=True)

    salida = {}
    for objetivo in ("media", "p90"):
        M = np.zeros((V.shape[0], HORIZONTE), np.float32)
        for bloque in range(4):
            ruta = os.path.join(DIRECTORIO, f"{objetivo}_bloque{bloque}.txt")
            m = lgb.Booster(model_file=ruta)
            min_lag = 7 * (bloque + 1)
            dias = range(n_real + 7 * bloque, n_real + 7 * (bloque + 1))
            X = construir_matriz(dias, V, P, cs, cal, meta, min_lag)
            M[X["serie"].values, X["dia"].values - n_real] = np.maximum(m.predict(a_float32(X)), 0)
            del X, m
        salida[objetivo] = M
        print(f"  {objetivo}: {M.sum():,.0f} unidades en 28 días  [{time.time()-t0:.0f}s]", flush=True)

    # el p90 nunca por debajo de la media: si se cruzan, gana el mayor
    salida["p90"] = np.maximum(salida["p90"], salida["media"])

    fechas = cal["fecha"].to_numpy()[n_real:n_real + HORIZONTE]
    n = V.shape[0]
    df = pd.DataFrame({
        "item": np.repeat(meta["item"].to_numpy(), HORIZONTE),
        "store_code": np.repeat(meta["store_code"].to_numpy(), HORIZONTE),
        "fecha": np.tile(fechas, n),
        "prediccion_media": salida["media"].ravel(),
        "prediccion_p90": salida["p90"].ravel(),
        "modelo_id": modelo_id,
    })
    destino = os.path.join(GOLD, "fact_predicciones.parquet")
    tmp = destino + ".tmp"
    df.to_parquet(tmp, index=False)
    os.replace(tmp, destino)
    print(f"\n{len(df):,} filas escritas en fact_predicciones  ·  "
          f"total {(time.time()-t0)/60:.1f} min")


if __name__ == "__main__":
    main()
