# -*- coding: utf-8 -*-
"""
DSMarket — cierre del ciclo: las salidas de los modelos vuelven al warehouse.

Escribe dos tablas de hechos en gold:
    fact_predicciones  una fila por producto-tienda-día con la predicción media y el p90
    fact_reposicion    una fila por revisión con el nivel objetivo y el pedido sugerido

Con esto el dashboard, la API y la app leen todos de la misma fuente, y no de ficheros
sueltos por ahí. Es lo que convierte cuatro notebooks en un sistema.
"""
import os, sys, time, logging
import numpy as np, pandas as pd, duckdb
from scipy.stats import norm

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pipeline import conectar, GOLD, CACHE, RAIZ, log

MODELO, VERSION = "lightgbm_bloques_tweedie", "v1"
R, L = 7, 2                       # ciclo de revisión y plazo de entrega
NIVEL_POR_CELDA = {'AX':.98,'AY':.95,'AZ':.90,'BX':.95,'BY':.90,'BZ':.85,'CX':.90,'CY':.85,'CZ':.80}

def cargar(con):
    meta = pd.read_csv(f"{CACHE}/meta.csv")
    media = np.load(f"{CACHE}/pred_futuro.npy")
    p90 = np.load(f"{CACHE}/p90_final.npy")
    ultima = con.execute("SELECT max(fecha) FROM dim_calendario").fetchone()[0]
    fechas = pd.date_range(pd.Timestamp(ultima) + pd.Timedelta(days=1), periods=media.shape[1])
    log.info(f"predicciones de {fechas[0].date()} a {fechas[-1].date()} para {media.shape[0]:,} series")

    # ---------- fact_predicciones ----------
    n_series, n_dias = media.shape
    pred = pd.DataFrame({
        'item': np.repeat(meta['item'].values, n_dias),
        'store_code': np.repeat(meta['store_code'].values, n_dias),
        'fecha': np.tile(fechas.values, n_series),
        'prediccion_media': media.ravel().round(4),
        'prediccion_p90': p90.ravel().round(4)})
    pred['modelo'] = MODELO; pred['version'] = VERSION
    pred['generado_en'] = pd.Timestamp.now().normalize()
    con.register('tmp_pred', pred)
    con.execute(f"""
        COPY (SELECT item || '|' || store_code AS serie_id, item, store_code,
                     CAST(fecha AS DATE) AS fecha, prediccion_media, prediccion_p90,
                     modelo, version, CAST(generado_en AS DATE) AS generado_en
              FROM tmp_pred)
        TO '{GOLD}/fact_predicciones.parquet' (FORMAT PARQUET, COMPRESSION ZSTD)""")
    log.info(f"  fact_predicciones           {len(pred):>12,} filas  "
             f"{os.path.getsize(f'{GOLD}/fact_predicciones.parquet')/1e6:.1f} MB")

    # ---------- fact_reposicion ----------
    # nivel objetivo = demanda esperada en la ventana de cobertura + stock de seguridad,
    # con el método que corresponde a cada segmento (política híbrida de la Tarea 4)
    serie = con.execute("SELECT item, store_code, clase_abc, clase_xyz FROM dim_serie").df()
    serie['celda'] = serie['clase_abc'] + serie['clase_xyz']
    orden = {(i, s): k for k, (i, s) in enumerate(zip(meta['item'], meta['store_code']))}
    serie['fila'] = [orden[(i, s)] for i, s in zip(serie['item'], serie['store_code'])]
    serie = serie.sort_values('fila').reset_index(drop=True)

    hist = con.execute(f"""
        SELECT item, store_code, fecha, unidades FROM fact_ventas
        WHERE fecha > DATE '{ultima}' - INTERVAL 180 DAY
    """).df().pivot_table(index=['item','store_code'], columns='fecha', values='unidades', fill_value=0)
    hist = hist.reindex(pd.MultiIndex.from_arrays([serie['item'], serie['store_code']])).fillna(0).to_numpy()
    ventanas = np.lib.stride_tricks.sliding_window_view(hist, R + L, axis=1).sum(axis=2)
    percentil_empirico = np.percentile(ventanas, 90, axis=1)

    sigma = np.maximum(p90 - media, 0) / norm.ppf(0.90)
    z = np.array([norm.ppf(NIVEL_POR_CELDA[c]) for c in serie['celda']])
    usa_empirico = (serie['clase_xyz'] == 'X').to_numpy()

    filas = []
    for t in range(0, n_dias, R):
        ventana = slice(t, min(t + R + L, n_dias))
        mu = media[:, ventana].sum(axis=1)
        sd = np.sqrt((sigma[:, ventana] ** 2).sum(axis=1))
        nivel_modelo = mu + z * sd
        nivel = np.where(usa_empirico, percentil_empirico, nivel_modelo)
        filas.append(pd.DataFrame({
            'fecha_revision': fechas[t], 'cobertura_dias': R + L,
            'item': serie['item'], 'store_code': serie['store_code'], 'segmento': serie['celda'],
            'demanda_esperada': mu.round(2), 'nivel_objetivo': np.ceil(nivel).astype(int),
            'stock_seguridad': np.ceil(nivel - mu).clip(0).astype(int),
            'nivel_servicio': [NIVEL_POR_CELDA[c] for c in serie['celda']],
            'metodo': np.where(usa_empirico, 'percentil_empirico', 'modelo_cuantilico')}))
    rep = pd.concat(filas, ignore_index=True)
    rep['modelo'] = MODELO; rep['version'] = VERSION
    con.register('tmp_rep', rep)
    con.execute(f"""
        COPY (SELECT item || '|' || store_code AS serie_id, item, store_code,
                     CAST(fecha_revision AS DATE) AS fecha_revision, cobertura_dias, segmento,
                     demanda_esperada, nivel_objetivo, stock_seguridad, nivel_servicio,
                     metodo, modelo, version
              FROM tmp_rep)
        TO '{GOLD}/fact_reposicion.parquet' (FORMAT PARQUET, COMPRESSION ZSTD)""")
    log.info(f"  fact_reposicion             {len(rep):>12,} filas  "
             f"{os.path.getsize(f'{GOLD}/fact_reposicion.parquet')/1e6:.1f} MB")

    for t in ('fact_predicciones', 'fact_reposicion'):
        con.execute(f"CREATE OR REPLACE VIEW {t} AS SELECT * FROM read_parquet('{GOLD}/{t}.parquet')")

if __name__ == "__main__":
    con = conectar()
    cargar(con)
    print()
    print(con.execute("""
        SELECT r.fecha_revision, r.segmento, count(*) AS series,
               round(sum(r.demanda_esperada)) AS demanda_esperada,
               sum(r.nivel_objetivo) AS nivel_objetivo, sum(r.stock_seguridad) AS stock_seguridad
        FROM fact_reposicion r GROUP BY 1,2 ORDER BY 1,2 LIMIT 9
    """).df().to_string(index=False))
    con.close()
