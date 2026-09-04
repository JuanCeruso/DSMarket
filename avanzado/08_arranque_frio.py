# -*- coding: utf-8 -*-
"""
Experimento 8 — Arranque en frío: predecir un producto que todavía no tiene histórico.

EL PROBLEMA
-----------
El 88% de la importancia del modelo está en las medias móviles. Un producto nuevo no las tiene:
llega al lineal sin retardos, sin media de 28 días y sin media anual. En la práctica el sistema
no puede decir cuánto pedir de él, que es justo el momento en que más falta hace acertar —una
referencia nueva mal dimensionada se agota el primer fin de semana o se queda en el almacén.

Es un problema real de distribución y hoy el proyecto no lo resuelve.

LA IDEA
-------
Si no hay historia propia, se usa la de los productos parecidos. Con los atributos que sí existen
el día del alta —categoría, departamento, tienda, ciudad, grupo de comportamiento de la tienda,
precio— se predice la **demanda media diaria** del producto y su **perfil semanal**, aprendiendo
de las 30.490 series que sí tienen historia.

Y hay una segunda vía que aprovecha lo que el proyecto ya tiene: **la misma referencia en otra
tienda**. Un producto nuevo en Brooklyn puede llevar dos años vendiéndose en Boston. El grupo de
comportamiento de tienda —el que reveló que Tribeca se parece a Boston— dice de qué tienda
conviene copiar.

CÓMO SE EVALÚA, Y POR QUÉ ESTO ES LO DIFÍCIL
--------------------------------------------
No basta con entrenar y medir: hay que **simular el desconocimiento**. Se toma un conjunto de
series con historia, se les oculta por completo, se predice como si fueran nuevas y se compara
con lo que realmente vendieron. Si se entrenara con esas series dentro, el resultado sería una
mentira: el modelo ya las conoce.

Por eso la partición es **por producto y no por fila**: ningún producto del conjunto de prueba
aparece en el de entrenamiento, en ninguna tienda.

Se compara contra las tres referencias que un encargado usaría de verdad:

    A  la media de la categoría en esa tienda
    B  la media del departamento en esa tienda
    C  la misma referencia en la tienda más parecida (si existe)
    D  el modelo por atributos          <- lo que se propone

    python3 avanzado/08_arranque_frio.py
    python3 avanzado/08_arranque_frio.py --productos-prueba 400
"""
import argparse, os, sys, time
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comun import conectar, SALIDA, mae, rmse
import lightgbm as lgb

VENTANA = 90          # dias sobre los que se mide la demanda media de cada serie


def cargar(con, ventana):
    return con.execute(f"""
        WITH ult AS (SELECT max(fecha) f FROM fact_ventas),
        base AS (
            SELECT v.item, v.store_code,
                   avg(v.unidades)                                   AS media_dia,
                   avg(v.precio)                                     AS precio,
                   sum(CASE WHEN dayofweek(v.fecha) IN (0,6) THEN v.unidades ELSE 0 END)
                     / nullif(sum(v.unidades), 0)                    AS peso_finde,
                   count(*)                                          AS dias
            FROM fact_ventas v, ult
            WHERE v.fecha > ult.f - INTERVAL {ventana} DAY
            GROUP BY 1, 2
        )
        SELECT b.*, p.categoria, p.departamento, p.arquetipo,
               t.ciudad, t.tienda, t.grupo_comportamiento
        FROM base b
        JOIN dim_producto p USING (item)
        JOIN dim_tienda   t USING (store_code)
        WHERE b.dias >= {ventana // 2}
    """).df()


def main(n_prueba, semilla):
    t0 = time.time()
    con = conectar()
    df = cargar(con, VENTANA)
    con.close()
    print(f"{len(df):,} series con historia · {df['item'].nunique():,} productos "
          f"[{time.time()-t0:.0f}s]", flush=True)

    rng = np.random.default_rng(semilla)
    productos = df["item"].unique()
    prueba = set(rng.choice(productos, min(n_prueba, len(productos) // 4), replace=False))
    ent = df[~df["item"].isin(prueba)].copy()
    tst = df[df["item"].isin(prueba)].copy()
    print(f"entrenamiento {len(ent):,} series · prueba {len(tst):,} series "
          f"({len(prueba)} productos ocultos por completo)\n", flush=True)

    # ---------- A y B: medias de catálogo en esa tienda ----------
    med_cat = ent.groupby(["store_code", "categoria"])["media_dia"].mean().rename("A")
    med_dep = ent.groupby(["store_code", "departamento"])["media_dia"].mean().rename("B")
    tst = tst.join(med_cat, on=["store_code", "categoria"]).join(med_dep, on=["store_code", "departamento"])

    # ---------- C: la misma referencia en la tienda más parecida ----------
    # (el producto está oculto en TODAS las tiendas, así que esta vía solo aplica cuando el
    #  producto ya existe en otra tienda: se simula ocultándolo solo en la tienda evaluada)
    vecina = {}
    for grupo, g in df.groupby("grupo_comportamiento"):
        tiendas = g["store_code"].unique()
        for s in tiendas:
            otras = [o for o in tiendas if o != s]
            vecina[s] = otras[0] if otras else None
    ref = df.set_index(["item", "store_code"])["media_dia"]
    tst["C"] = [ref.get((it, vecina.get(sc)), np.nan)
                for it, sc in zip(tst["item"], tst["store_code"])]

    # ---------- D: modelo por atributos ----------
    cats = ["categoria", "departamento", "ciudad", "grupo_comportamiento", "store_code"]
    for c in cats:
        codigos = pd.Categorical(pd.concat([ent[c], tst[c]]).astype(str)).categories
        ent[c + "_id"] = pd.Categorical(ent[c].astype(str), categories=codigos).codes
        tst[c + "_id"] = pd.Categorical(tst[c].astype(str), categories=codigos).codes
    feats = [c + "_id" for c in cats] + ["precio"]

    d = lgb.Dataset(ent[feats].to_numpy(np.float32),
                    label=np.log1p(ent["media_dia"].to_numpy(np.float32)),
                    feature_name=feats, categorical_feature=[c + "_id" for c in cats])
    m = lgb.train(dict(objective="regression", metric="l2", learning_rate=0.05, num_leaves=64,
                       min_data_in_leaf=50, feature_fraction=0.9, num_threads=4, verbose=-1,
                       seed=42), d, num_boost_round=400)
    tst["D"] = np.expm1(m.predict(tst[feats].to_numpy(np.float32))).clip(0)

    # ---------- resultados ----------
    y = tst["media_dia"].to_numpy(float)
    nombres = {"A": "media de la categoría en la tienda",
               "B": "media del departamento en la tienda",
               "C": "misma referencia en la tienda vecina",
               "D": "modelo por atributos"}
    filas = []
    for k, nombre in nombres.items():
        p = tst[k].to_numpy(float)
        v = np.isfinite(p)
        filas.append({"referencia": nombre, "cobertura_%": v.mean() * 100,
                      "MAE": mae(y[v], p[v]), "RMSE": rmse(y[v], p[v]),
                      "sesgo_%": (p[v].sum() - y[v].sum()) / max(y[v].sum(), 1) * 100})
    res = pd.DataFrame(filas)
    print("=== PREDICCIÓN DE LA DEMANDA MEDIA DIARIA DE UN PRODUCTO NUEVO ===")
    print(res.round(3).to_string(index=False))

    mejor = res.loc[res["MAE"].idxmin(), "referencia"]
    ganancia = (res.loc[res["referencia"] == nombres["A"], "MAE"].iloc[0] - res["MAE"].min())
    print(f"\n  mejor: «{mejor}»")
    print(f"  mejora sobre la media de categoría: {ganancia:.4f} unidades/día de MAE "
          f"({ganancia / res.loc[res['referencia']==nombres['A'],'MAE'].iloc[0] * 100:.1f}%)")

    # ---------- por dónde falla ----------
    tst["error_D"] = np.abs(tst["D"] - tst["media_dia"])
    por_cat = tst.groupby("categoria").agg(series=("item", "count"),
                                           demanda_real=("media_dia", "mean"),
                                           mae_D=("error_D", "mean")).round(3)
    print("\n=== DÓNDE FALLA EL MODELO POR ATRIBUTOS ===")
    print(por_cat.to_string())

    res.to_csv(os.path.join(SALIDA, "arranque_frio.csv"), index=False)
    por_cat.to_csv(os.path.join(SALIDA, "arranque_frio_por_categoria.csv"))
    print(f"""
CÓMO LEERLO
-----------
Lo relevante no es cuánto gana el modelo, es **cuánto gana sobre lo que haría un encargado**. Si
la media de la categoría en la tienda ya se acerca, la conclusión honesta es que para un producto
nuevo una regla simple basta, y eso también se escribe.

Mirá sobre todo la columna de cobertura de la vía C: solo aplica cuando el producto ya se vende
en otra tienda del mismo grupo de comportamiento. Cuando aplica suele ser la mejor, y eso conecta
directamente con el hallazgo de §7.2 —que el grupo de tienda cruza las fronteras de ciudad—: el
agrupamiento no era un adorno descriptivo, sirve para decidir de qué tienda copiar.

Y la limitación que hay que declarar: esto predice el **nivel medio**, no la serie diaria. Para
las primeras semanas de un producto nuevo es suficiente, porque la política de reposición solo
necesita la demanda del ciclo. En cuanto la referencia acumula cuatro semanas de historia, el
modelo general la absorbe y esto deja de usarse.

guardado en {SALIDA}  ·  total {time.time()-t0:.0f}s""")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--productos-prueba", dest="n_prueba", type=int, default=300)
    ap.add_argument("--semilla", type=int, default=42)
    a = ap.parse_args()
    main(a.n_prueba, a.semilla)
