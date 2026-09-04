# -*- coding: utf-8 -*-
"""
Experimento 9 — Surtido: qué referencias son candidatas a salir del catálogo.

POR QUÉ ESTA PREGUNTA
---------------------
DSMarket no la hizo, pero es la consecuencia directa de la matriz ABC/XYZ de la Tarea 2: la celda
CZ concentra cerca del 28% del catálogo por el 3,5% de la facturación. Para esas referencias la
pregunta pertinente no es cuánto reponer sino **si vale la pena mantenerlas**, y la política de
reposición no puede responderla porque da por dado el surtido.

Es además la recomendación con efecto más inmediato: retirar una referencia libera lineal,
simplifica la reposición y elimina un stock de seguridad que no rota.

EL CRITERIO, Y POR QUÉ NO ES SOLO «VENDE POCO»
----------------------------------------------
Vender poco no basta para descatalogar. Se combinan cinco señales, y dos de ellas son frenos:

    facturación        peso en el negocio de la tienda (poco = candidata)
    tendencia          pendiente de los últimos 12 meses (cayendo = candidata)
    intermitencia      fracción de días sin venta (alta = candidata)
    exclusividad  ↩    si es de las pocas referencias de su departamento en esa tienda, NO
    fidelidad     ↩    si la venden pocas tiendas pero en esas rota bien, NO

Las dos últimas son las que evitan el error clásico de este análisis: descatalogar el único
producto de una familia, o retirar de la red algo que en una tienda concreta funciona. Un ranking
que solo mira facturación los comete siempre.

LO QUE ESTO NO ES
-----------------
No es una decisión: es una **lista de candidatas a revisar**. Sin datos de margen por referencia,
de coste de lineal ni de sustitución entre productos, ningún modelo puede decidir un surtido. Lo
que sí puede es ordenar 30.490 series para que una persona mire cincuenta en vez de treinta mil.

    python3 avanzado/09_surtido.py
    python3 avanzado/09_surtido.py --top 100 --margen 0.25
"""
import argparse, os, sys, time
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comun import conectar, SALIDA


def main(top, margen, coste_lineal_dia):
    t0 = time.time()
    con = conectar()
    print("calculando señales…", flush=True)
    df = con.execute("""
        WITH ult AS (SELECT max(fecha) f FROM fact_ventas),
        anual AS (
            SELECT v.item, v.store_code,
                   sum(v.importe)                                        AS facturacion_365,
                   sum(v.unidades)                                       AS unidades_365,
                   avg(CASE WHEN v.unidades = 0 THEN 1.0 ELSE 0.0 END)   AS frac_sin_venta,
                   sum(CASE WHEN v.fecha > ult.f - INTERVAL 182 DAY THEN v.importe ELSE 0 END)
                                                                          AS fact_reciente,
                   sum(CASE WHEN v.fecha <= ult.f - INTERVAL 182 DAY THEN v.importe ELSE 0 END)
                                                                          AS fact_previa,
                   avg(v.precio)                                          AS precio
            FROM fact_ventas v, ult
            WHERE v.fecha > ult.f - INTERVAL 365 DAY
            GROUP BY 1, 2
        ),
        depto AS (   -- cuántas referencias tiene ese departamento en esa tienda
            SELECT a.store_code, p.departamento, count(*) AS refs_departamento
            FROM anual a JOIN dim_producto p USING (item)
            GROUP BY 1, 2
        ),
        red AS (     -- en cuántas tiendas se vende esa referencia
            SELECT item, count(*) AS tiendas_con_venta, avg(unidades_365) AS uds_medias_red
            FROM anual GROUP BY 1
        )
        SELECT a.*, p.categoria, p.departamento, p.arquetipo,
               t.tienda, t.ciudad,
               s.clase_abc, s.clase_xyz, s.clase_abc || s.clase_xyz AS segmento,
               d.refs_departamento, r.tiendas_con_venta, r.uds_medias_red
        FROM anual a
        JOIN dim_producto p USING (item)
        JOIN dim_tienda   t USING (store_code)
        JOIN dim_serie    s USING (item, store_code)
        JOIN depto d ON d.store_code = a.store_code AND d.departamento = p.departamento
        JOIN red   r ON r.item = a.item
    """).df()
    con.close()
    print(f"  {len(df):,} series  [{time.time()-t0:.0f}s]\n", flush=True)

    # ---------- señales normalizadas a [0,1], donde 1 = más candidata ----------
    def rango(x, invertir=False):
        r = pd.Series(x).rank(pct=True).to_numpy()
        return 1 - r if invertir else r

    df["s_facturacion"] = rango(df["facturacion_365"], invertir=True)
    tend = (df["fact_reciente"] - df["fact_previa"]) / df["fact_previa"].replace(0, np.nan)
    df["tendencia_semestral"] = tend
    df["s_tendencia"] = rango(tend.fillna(0), invertir=True)
    df["s_intermitencia"] = rango(df["frac_sin_venta"])
    # frenos
    df["s_exclusividad"] = rango(df["refs_departamento"])          # pocas refs -> NO retirar
    df["s_fidelidad"] = rango(df["unidades_365"] / df["uds_medias_red"].replace(0, np.nan))

    df["indice_retirada"] = (0.35 * df["s_facturacion"]
                             + 0.25 * df["s_tendencia"]
                             + 0.20 * df["s_intermitencia"]
                             + 0.10 * df["s_exclusividad"]
                             - 0.20 * df["s_fidelidad"]).clip(0, 1)

    # ---------- lo que se libera ----------
    df["coste_lineal_365"] = coste_lineal_dia * 365
    df["margen_365"] = df["facturacion_365"] * margen
    df["margen_neto"] = df["margen_365"] - df["coste_lineal_365"]

    cand = df.sort_values("indice_retirada", ascending=False).head(top)
    print("=== CANDIDATAS A REVISAR ===")
    cols = ["item", "tienda", "segmento", "facturacion_365", "tendencia_semestral",
            "frac_sin_venta", "tiendas_con_venta", "indice_retirada"]
    print(cand[cols].head(25).round(3).to_string(index=False))

    print("\n=== COMPOSICIÓN DE LAS CANDIDATAS ===")
    print(cand.groupby("segmento").size().rename("series").to_string())
    print(f"\n  facturación anual que representan : {cand['facturacion_365'].sum():>12,.0f} USD")
    print(f"  margen anual que representan      : {cand['margen_365'].sum():>12,.0f} USD")
    print(f"  % de la facturación de la cadena  : "
          f"{cand['facturacion_365'].sum()/df['facturacion_365'].sum()*100:>12.2f} %")

    # ---------- el freno, comprobado ----------
    print("\n=== EL FRENO, COMPROBADO ===")
    sin_freno = df.sort_values("facturacion_365").head(top)
    solapan = len(set(zip(cand["item"], cand["store_code"])) &
                  set(zip(sin_freno["item"], sin_freno["store_code"])))
    print(f"  Un ranking que solo mirara facturación propondría {top} series.")
    print(f"  Coinciden con estas: {solapan} de {top} ({solapan/top*100:.0f}%).")
    excluidas = sin_freno[~sin_freno.set_index(['item','store_code']).index.isin(
        cand.set_index(['item','store_code']).index)]
    if len(excluidas):
        print(f"\n  Las {len(excluidas)} que el criterio simple habría retirado y este no, "
              f"por qué se salvan:")
        print(f"    · media de referencias en su departamento y tienda: "
              f"{excluidas['refs_departamento'].mean():.1f} "
              f"(frente a {cand['refs_departamento'].mean():.1f} en las candidatas)")
        print(f"    · venden {excluidas['unidades_365'].mean()/max(excluidas['uds_medias_red'].mean(),1e-9):.2f} "
              f"veces la media de la red para esa referencia")

    cand.to_csv(os.path.join(SALIDA, "surtido_candidatas.csv"), index=False)
    df.to_csv(os.path.join(SALIDA, "surtido_indice_completo.csv"), index=False)
    print(f"""
CÓMO USARLO
-----------
Esto ordena, no decide. La salida es una lista de {top} series para que alguien de comercial mire
cincuenta en vez de treinta mil, y la comprobación del freno es la parte que hay que enseñar: un
ranking por facturación y este coinciden solo en parte, y la diferencia son exactamente las
referencias que no hay que tocar —las últimas de su departamento en esa tienda, o las que en esa
tienda concreta rotan mejor que en el resto de la red.

Lo que falta para convertirlo en decisión, y hay que decirlo: margen por referencia, coste de
ocupación de lineal y efecto de sustitución. Sin lo tercero, retirar dos productos que compiten
entre sí no ahorra el doble.

guardado en {SALIDA}  ·  total {time.time()-t0:.0f}s""")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=100, help="cuántas candidatas listar")
    ap.add_argument("--margen", type=float, default=0.25)
    ap.add_argument("--coste-lineal-dia", type=float, default=0.02,
                    help="coste diario de ocupar lineal por referencia, en USD")
    a = ap.parse_args()
    main(a.top, a.margen, a.coste_lineal_dia)
