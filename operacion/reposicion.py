# -*- coding: utf-8 -*-
"""
Etapa de reposición.

Convierte las predicciones en niveles objetivo por serie y escribe `fact_reposicion`. Aplica la
misma política híbrida que la API y el panel: el término de incertidumbre sale del desvío
histórico en las series de clase X y del modelo cuantílico en las Y y Z.

Esta etapa no decide el pedido —para eso hace falta el stock, que el sistema no tiene—: deja
calculado el nivel objetivo, que es la parte que sí depende de los datos.

    python3 operacion/reposicion.py --dias-revision 7 --lead-time 2
"""
from __future__ import annotations
import argparse, os, time
import numpy as np, pandas as pd
from scipy.stats import norm
from base import GOLD, conectar

# La política vive en politica.py, donde no tiene un almacén alrededor y por tanto se puede
# probar. Aquí se importa: dos copias de la misma tabla de niveles de servicio acabarían
# divergiendo, y la que estuviera mal sería siempre la que corre en producción.
from politica import NIVEL_POR_CATEGORIA, ALFA_CUANTIL, nivel_servicio


def main(dias_revision, lead_time):
    t0 = time.time()
    cobertura = dias_revision + lead_time
    con = conectar()
    cols = [r[0] for r in con.execute("DESCRIBE fact_predicciones").fetchall()]
    modelo_sql = ("any_value(modelo_id) AS modelo_id" if "modelo_id" in cols
                  else "'sin_registrar' AS modelo_id")
    df = con.execute(f"""
        WITH ventana AS (
            SELECT item, store_code,
                   sum(prediccion_media) AS demanda,
                   sqrt(sum(pow(greatest(prediccion_p90 - prediccion_media, 0), 2))) AS sigma_modelo,
                   min(fecha) AS desde, max(fecha) AS hasta,
                   {modelo_sql}
            FROM (SELECT *, row_number() OVER (PARTITION BY item, store_code ORDER BY fecha) rn
                  FROM fact_predicciones)
            WHERE rn <= {cobertura}
            GROUP BY 1, 2
        )
        SELECT v.*, s.media_dia, s.desvio_dia, s.clase_abc, s.clase_xyz,
               s.clase_abc || s.clase_xyz AS segmento
        FROM ventana v JOIN dim_serie s USING (item, store_code)
    """).df()
    con.close()
    if df.empty:
        raise SystemExit("No hay predicciones cargadas. Ejecutá antes: python3 operacion/predecir.py")

    df["nivel_servicio"] = df["item"].map(nivel_servicio)
    z = norm.ppf(df["nivel_servicio"].to_numpy())

    # sigma del modelo cuantílico: (p90 - media) / z_{0.90}, agregado en cuadratura
    sigma_modelo = df["sigma_modelo"].to_numpy() / norm.ppf(ALFA_CUANTIL)
    sigma_hist = df["desvio_dia"].to_numpy() * np.sqrt(cobertura)
    es_x = (df["clase_xyz"] == "X").to_numpy()

    df["metodo"] = np.where(es_x, "percentil empírico (histórico)", "modelo cuantílico")
    demanda = np.where(es_x, df["media_dia"].to_numpy() * cobertura, df["demanda"].to_numpy())
    sigma = np.where(es_x, sigma_hist, sigma_modelo)

    df["demanda_esperada"] = np.maximum(demanda, 0)
    df["stock_seguridad"] = np.maximum(z * sigma, 0)
    df["nivel_objetivo"] = df["demanda_esperada"] + df["stock_seguridad"]
    df["fecha_revision"] = df["desde"]
    df["dias_cobertura"] = cobertura

    cols = ["fecha_revision", "item", "store_code", "segmento", "demanda_esperada",
            "nivel_objetivo", "stock_seguridad", "nivel_servicio", "metodo",
            "dias_cobertura", "modelo_id"]
    destino = os.path.join(GOLD, "fact_reposicion.parquet")
    tmp = destino + ".tmp"
    df[cols].to_parquet(tmp, index=False)
    os.replace(tmp, destino)

    resumen = df.groupby("segmento").agg(
        series=("item", "count"),
        demanda=("demanda_esperada", "sum"),
        seguridad=("stock_seguridad", "sum")).round(0)
    print(f"cobertura de {cobertura} días ({dias_revision} de revisión + {lead_time} de plazo)\n")
    print(resumen.to_string())
    print(f"\n{len(df):,} filas escritas en fact_reposicion  ·  {time.time()-t0:.0f}s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dias-revision", type=int, default=7)
    ap.add_argument("--lead-time", type=int, default=2)
    a = ap.parse_args()
    main(a.dias_revision, a.lead_time)
