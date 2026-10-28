# -*- coding: utf-8 -*-
"""
Etapa de reposición.

Convierte las predicciones en niveles objetivo por serie y escribe `fact_reposicion`. Aplica la
misma política híbrida que la API, la app y el notebook 04: percentil empírico del histórico en
las series de clase X y demanda predicha más stock de seguridad del modelo cuantílico en las Y y Z.

Esta etapa no decide el pedido —para eso hace falta el stock, que el sistema no tiene—: deja
calculado el nivel objetivo, que es la parte que sí depende de los datos.

    python3 operacion/reposicion.py --dias-revision 7 --lead-time 2
"""
from __future__ import annotations
import argparse, os, time
import numpy as np, pandas as pd
from base import GOLD, conectar

# La política vive en politica.py, donde no tiene un almacén alrededor y por tanto se puede
# probar. Aquí se importa: dos copias de la misma tabla de niveles de servicio acabarían
# divergiendo, y la que estuviera mal sería siempre la que corre en producción.
import politica as pol
from historia import historia_reciente


def main(dias_revision, lead_time):
    t0 = time.time()
    cobertura = dias_revision + lead_time
    if cobertura > 28:
        raise SystemExit("La cobertura (revisión + plazo) no puede superar los 28 días de predicción.")
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

    df["nivel_servicio"] = df["item"].map(pol.nivel_servicio)
    niveles = df["nivel_servicio"].to_numpy()
    es_x = (df["clase_xyz"] == "X").to_numpy()

    # percentil empírico de las ventas en ventanas de `cobertura` días (series estables)
    fila_de, hist = historia_reciente(GOLD, pol.VENTANA_HISTORIA)
    H = hist[[fila_de[f"{i}|{s}"] for i, s in zip(df["item"], df["store_code"])]]
    empirico = pol.percentil_empirico(H, cobertura, niveles)

    # incertidumbre del modelo cuantílico: (p90 - media) / z_0.90, agregada en cuadratura
    sigma_modelo = df["sigma_modelo"].to_numpy() / pol.norm.ppf(pol.ALFA_CUANTIL)
    nivel = pol.nivel_hibrido(df["demanda"].to_numpy(), sigma_modelo, niveles, es_x, empirico)

    df["metodo"] = np.where(es_x, "percentil_empirico", "modelo_cuantilico")
    df["demanda_esperada"] = np.maximum(df["demanda"].to_numpy(), 0)
    df["nivel_objetivo"] = nivel
    df["stock_seguridad"] = np.maximum(nivel - df["demanda_esperada"], 0)
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
