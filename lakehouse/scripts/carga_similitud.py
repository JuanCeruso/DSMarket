# -*- coding: utf-8 -*-
"""
DSMarket — similitud entre tiendas (cuaderno 02, sección 5) en la capa gold.

Escribe dos tablas:

    mart_tienda_perfil      una fila por tienda y variable de perfil: valor real y desviaciones respecto
                            a la media de las 10 tiendas (z). Alimenta el mapa de calor del panel.
    mart_tienda_distancia   una fila por pareja de tiendas: distancia euclídea entre sus perfiles
                            (menor = más parecidas). Alimenta la matriz de parecido del panel.

Las seis variables de perfil son las del cuaderno 02: variabilidad diaria, fin de semana frente a
entre semana, diciembre frente al resto del año, índice de precio, % supermercado y % hogar. El volumen
se excluye: mide el tamaño de la tienda, no su forma de vender.

Salida: lakehouse/gold/*.parquet y lakehouse/gold_csv/*.csv
"""
import os
import numpy as np
import pandas as pd
from pipeline import conectar, GOLD, RAIZ

CSV = os.path.join(RAIZ, "gold_csv")
VARIABLES = {"cv_diaria": "Variabilidad diaria", "fin_semana": "Fin de semana vs. entre semana",
             "diciembre": "Diciembre vs. resto del año", "indice_precio": "Índice de precio (%)",
             "pct_alimentacion": "% supermercado", "pct_hogar": "% hogar"}


def main():
    con = conectar()
    dia = con.execute("""
        SELECT v.store_code, v.fecha, sum(v.unidades) AS u, c.es_fin_de_semana AS fds, c.mes
        FROM mart_ventas_dia v JOIN dim_calendario c USING (fecha) GROUP BY ALL""").df()
    m = dia.pivot(index="store_code", columns="fecha", values="u").fillna(0.0)
    cal = dia.drop_duplicates("fecha").set_index("fecha").loc[m.columns]
    fds, dic = cal["fds"].astype(bool).values, (cal["mes"] == 12).values
    v = m.values
    f = pd.DataFrame({"cv_diaria": v.std(axis=1) / v.mean(axis=1),
                      "fin_semana": v[:, fds].mean(axis=1) / v[:, ~fds].mean(axis=1),
                      "diciembre": v[:, dic].mean(axis=1) / v[:, ~dic].mean(axis=1)}, index=m.index)
    f["indice_precio"] = con.execute("SELECT store_code, indice_precio_pct FROM mart_precios_tienda").df().set_index("store_code")["indice_precio_pct"]
    cat = con.execute("""SELECT store_code, categoria, sum(unidades) u FROM mart_ventas_dia GROUP BY ALL""").df().pivot(index="store_code", columns="categoria", values="u")
    cat = cat.div(cat.sum(axis=1), axis=0) * 100
    f["pct_alimentacion"], f["pct_hogar"] = cat["SUPERMARKET"], cat["HOME_&_GARDEN"]
    z = (f - f.mean()) / f.std()
    tienda = con.execute("SELECT store_code, tienda, ciudad FROM dim_tienda").df().set_index("store_code")

    largo = []
    for k, (c, etiqueta) in enumerate(VARIABLES.items(), start=1):
        for s in f.index:
            largo.append((s, tienda.loc[s, "tienda"], tienda.loc[s, "ciudad"], etiqueta, k, round(float(f.loc[s, c]), 4), round(float(z.loc[s, c]), 4)))
    perfil = pd.DataFrame(largo, columns=["store_code", "tienda", "ciudad", "variable", "orden_variable", "valor", "z"])
    D = np.sqrt(((z.values[:, None, :] - z.values[None, :, :]) ** 2).sum(axis=2))
    filas = []
    for i, a in enumerate(f.index):
        orden = np.argsort(D[i]); rank = {f.index[j]: r for r, j in enumerate(orden)}   # 0 = ella misma
        for j, b in enumerate(f.index):
            filas.append((a, tienda.loc[a, "tienda"], b, tienda.loc[b, "tienda"], round(float(D[i, j]), 4), rank[b]))
    dist = pd.DataFrame(filas, columns=["store_code", "tienda", "store_code_otra", "tienda_otra", "distancia", "orden_parecido"])

    os.makedirs(CSV, exist_ok=True)
    for nombre, df in (("mart_tienda_perfil", perfil), ("mart_tienda_distancia", dist)):
        con.register("tmp_df", df)
        con.execute(f"COPY (SELECT * FROM tmp_df) TO '{GOLD}/{nombre}.parquet' (FORMAT PARQUET, COMPRESSION ZSTD)")
        con.unregister("tmp_df")
        con.execute(f"CREATE OR REPLACE VIEW {nombre} AS SELECT * FROM read_parquet('{GOLD}/{nombre}.parquet')")
        con.execute(f"COPY (SELECT * FROM {nombre}) TO '{CSV}/{nombre}.csv' (HEADER, DELIMITER ',')")
        print(f"  {nombre:24s} {len(df):>6,} filas")
    # control: la tienda más parecida debe coincidir con dim_tienda
    mas = dist[dist.orden_parecido == 1].set_index("store_code")["store_code_otra"]
    ref = tienda.join(con.execute("SELECT store_code, tienda_mas_parecida FROM dim_tienda").df().set_index("store_code"))["tienda_mas_parecida"]
    difiere = [s for s in mas.index if mas[s] != ref[s]]
    print("  coincide con dim_tienda.tienda_mas_parecida:", "sí" if not difiere else f"NO en {difiere}")


if __name__ == "__main__":
    main()
