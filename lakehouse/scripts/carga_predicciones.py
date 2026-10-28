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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pipeline import conectar, GOLD, CACHE, PROYECTO, log

sys.path.insert(0, os.path.join(PROYECTO, "operacion"))
import politica as pol
from historia import historia_reciente

MODELO, VERSION = "lightgbm_400d_eventos_semanales", "v2"
R, L = 7, 2                       # ciclo de revisión y plazo de entrega
# La política (niveles de servicio por categoría, percentil empírico, nivel híbrido) vive en
# operacion/politica.py. Aquí solo se aplica: una sola copia de la regla, para que el almacén,
# la API, la app y el notebook 04 no puedan divergir.


def cargar(con):
    meta = pd.read_csv(f"{CACHE}/meta.csv")
    # modelo final de la Tarea 3 (notebook 03, sección 12): 400 días + eventos semanales
    media = np.load(f"{CACHE}/final_futuro_media.npy")
    p90 = np.maximum(np.load(f"{CACHE}/final_futuro_p90.npy"), media)
    ultima = con.execute("SELECT max(fecha) FROM dim_calendario WHERE NOT es_futuro").fetchone()[0]
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

    fila_de, hist_total = historia_reciente(GOLD, pol.VENTANA_HISTORIA)
    hist = np.vstack([hist_total[fila_de[f"{i}|{s}"]] for i, s in zip(serie['item'], serie['store_code'])])
    niveles = np.array([pol.nivel_servicio(i) for i in serie['item']])
    percentil_empirico = pol.percentil_empirico(hist, R + L, niveles)

    sigma = pol.sigma_desde_cuantil(p90, media)
    usa_empirico = (serie['clase_xyz'] == 'X').to_numpy()
    # la última revisión cubre más días de los que quedan predichos: se completa la ventana
    media_ext = np.hstack([media, np.zeros((n_series, R + L))])
    media_ext[:, n_dias:] = pol.completar_ventana(media, n_dias + R + L)[:, n_dias:]
    sigma_ext = np.hstack([sigma, np.zeros((n_series, R + L))])
    sigma_ext[:, n_dias:] = pol.completar_ventana(sigma, n_dias + R + L)[:, n_dias:]

    filas = []
    for t in range(0, n_dias, R):
        ventana = slice(t, t + R + L)
        mu = media_ext[:, ventana].sum(axis=1)
        sd = np.sqrt((sigma_ext[:, ventana] ** 2).sum(axis=1))
        nivel = pol.nivel_hibrido(mu, sd, niveles, usa_empirico, percentil_empirico)
        filas.append(pd.DataFrame({
            'fecha_revision': fechas[t], 'cobertura_dias': R + L,
            'item': serie['item'], 'store_code': serie['store_code'], 'segmento': serie['celda'],
            'demanda_esperada': mu.round(2), 'nivel_objetivo': np.ceil(nivel).astype(int),
            'stock_seguridad': np.ceil(nivel - mu).clip(0).astype(int),
            'nivel_servicio': niveles,
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
