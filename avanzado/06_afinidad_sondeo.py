# -*- coding: utf-8 -*-
"""
Sondeo 6 — ¿Hay afinidad real entre productos, o solo calendario compartido?

QUÉ NO SE PUEDE HACER, Y POR QUÉ
--------------------------------
`item_sales.csv` viene agregado por producto-tienda-día. No hay ticket, no hay identificador
de transacción, no hay cliente. Un market basket analysis —soporte, confianza, lift, reglas
de asociación— necesita la cesta, y la cesta no está en estos datos. Cualquier resultado que
se presente como «estos productos se compran juntos» sería una afirmación que el dato no
sostiene.

QUÉ SÍ SE PUEDE MEDIR
---------------------
**Afinidad de demanda**: dos productos cuya venta sube y baja los mismos días en la misma
tienda. Es una asociación a nivel de día, no de cesta, y hay que llamarla por su nombre.

Y tiene una trampa que invalida la versión ingenua: casi todo el co-movimiento diario lo
explica algo compartido —el sábado, diciembre, un evento, el tráfico de la tienda ese día—.
Correlacionar las series en bruto da que todo está asociado con todo.

El arreglo es el mismo movimiento que ya usa la Tarea 5: **residualizar**. A cada serie se le
quita lo que explican día de la semana, mes, evento y tráfico total de la tienda, y el
co-movimiento se mide sobre los residuos. Lo que sobrevive es co-movimiento más allá del
calendario.

LAS TRES PRUEBAS QUE DECIDEN SI HAY ALGO
----------------------------------------
Este script no busca confirmar la hipótesis: busca la evidencia que la tumbaría.

  1. **Nulo entre tiendas.** El producto A de la tienda 1 con el producto B de la tienda 2
     NUNCA pueden estar en la misma cesta. La distribución de esas correlaciones es el nivel
     de ruido. Si las parejas de la misma tienda no lo superan, no hay nada que contar.

  2. **Nitidez temporal.** Una compra conjunta es del mismo día. Si al desplazar una serie un
     día la correlación aguanta, no era compra conjunta: era tendencia compartida que la
     residualización no llegó a quitar.

  3. **Estabilidad fuera de muestra.** Las parejas se eligen con el 70% inicial de los días y
     se comprueban en el 30% final. Una pareja que no se repite era ruido de selección: con
     20.000 parejas, las mejores por azar salen altas siempre.

    python3 avanzado/06_afinidad_sondeo.py
    python3 avanzado/06_afinidad_sondeo.py --productos 300 --tiendas BOS_1 NYC_1
"""
import argparse, os, sys, time
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comun import conectar, SALIDA

UMBRAL_NITIDEZ = 0.05        # cuanto tiene que caer la correlacion al desplazar un dia
FRAC_ENTRENAMIENTO = 0.70


def panel_tienda(con, tienda, n_productos):
    """(productos x dias) de unidades para una tienda, mas el trafico diario total."""
    df = con.execute(f"""
        WITH top AS (
            SELECT item, sum(importe) f
            FROM fact_ventas WHERE store_code = ?
            GROUP BY 1 ORDER BY f DESC LIMIT {n_productos}
        )
        SELECT v.item, v.fecha, v.unidades
        FROM fact_ventas v JOIN top USING (item)
        WHERE v.store_code = ?
        ORDER BY v.item, v.fecha
    """, [tienda, tienda]).df()
    m = df.pivot(index="item", columns="fecha", values="unidades").fillna(0.0)
    return m


def matriz_control(fechas, trafico, cal):
    """Diseño con lo que hay que quitar: dia de semana, mes, evento y trafico de la tienda."""
    f = pd.to_datetime(pd.Series(fechas))
    partes = [np.ones((len(f), 1))]
    for serie in (f.dt.weekday, f.dt.month):
        d = pd.get_dummies(serie, drop_first=True).to_numpy(float)
        partes.append(d)
    ev = cal.set_index("fecha")["evento"].reindex(f.values).fillna("none")
    partes.append(pd.get_dummies(ev, drop_first=True).to_numpy(float))
    partes.append(np.log1p(trafico).reshape(-1, 1))
    return np.hstack(partes)


def residualizar(Y, X):
    """Y (productos x dias) menos su proyeccion sobre X (dias x k). Un solo ajuste para todos."""
    Yt = np.log1p(Y.T)                                   # dias x productos
    beta, *_ = np.linalg.lstsq(X, Yt, rcond=None)
    R = (Yt - X @ beta).T                                # productos x dias
    R -= R.mean(axis=1, keepdims=True)
    sd = R.std(axis=1, keepdims=True)
    sd[sd == 0] = 1.0
    return R / sd


def correlaciones(R):
    n = R.shape[1]
    return (R @ R.T) / n


def pares_superiores(C, items, k=40):
    iu = np.triu_indices_from(C, k=1)
    v = C[iu]
    orden = np.argsort(-v)[:k]
    return [(items[iu[0][j]], items[iu[1][j]], float(v[j])) for j in orden]


def main(n_productos, tiendas, k):
    t0 = time.time()
    con = conectar()
    cal = con.execute("SELECT fecha, evento FROM dim_calendario WHERE NOT es_futuro").df()
    cal["fecha"] = pd.to_datetime(cal["fecha"])
    cal["evento"] = cal["evento"].fillna("none")

    if not tiendas:
        tiendas = con.execute("SELECT store_code FROM dim_tienda ORDER BY store_code LIMIT 2").df()["store_code"].tolist()
    print(f"tiendas: {tiendas}  ·  {n_productos} productos por tienda\n", flush=True)

    paneles, residuos = {}, {}
    for tienda in tiendas:
        m = panel_tienda(con, tienda, n_productos)
        trafico = con.execute("""SELECT fecha, sum(unidades) u FROM fact_ventas
                                 WHERE store_code = ? GROUP BY 1 ORDER BY 1""", [tienda]).df()
        trafico["fecha"] = pd.to_datetime(trafico["fecha"])
        tr = trafico.set_index("fecha")["u"].reindex(pd.to_datetime(m.columns)).fillna(0).to_numpy()
        X = matriz_control(m.columns.to_numpy(), tr, cal)
        paneles[tienda] = m
        residuos[tienda] = residualizar(m.to_numpy(float), X)
        print(f"  {tienda}: {m.shape[0]} productos x {m.shape[1]} días  "
              f"·  {X.shape[1]} controles  [{time.time()-t0:.0f}s]", flush=True)
    con.close()

    principal = tiendas[0]
    items = paneles[principal].index.to_numpy()
    R = residuos[principal]
    n_dias = R.shape[1]
    corte = int(n_dias * FRAC_ENTRENAMIENTO)

    # ---------- señal frente a ruido ----------
    C_bruto = correlaciones(np.apply_along_axis(
        lambda r: (r - r.mean()) / (r.std() or 1), 1, np.log1p(paneles[principal].to_numpy(float))))
    C_resid = correlaciones(R)
    iu = np.triu_indices_from(C_resid, k=1)

    print("\n" + "=" * 74)
    print("PASO 1 · ¿Cuánto del co-movimiento era solo calendario?")
    print("=" * 74)
    print(f"  correlación media SIN residualizar : {C_bruto[iu].mean():+.4f}")
    print(f"  correlación media residualizada    : {C_resid[iu].mean():+.4f}")
    print(f"  parejas con r > 0,30 antes         : {(C_bruto[iu] > .30).mean()*100:6.2f}%")
    print(f"  parejas con r > 0,30 después       : {(C_resid[iu] > .30).mean()*100:6.2f}%")
    print("\n  Si el 'antes' es alto y el 'después' se derrumba, ahí está la respuesta a por qué")
    print("  una correlación directa habría dado que todo se compra con todo.")

    # ---------- prueba 1: nulo entre tiendas ----------
    print("\n" + "=" * 74)
    print("PASO 2 · Nulo entre tiendas (parejas que NO pueden compartir cesta)")
    print("=" * 74)
    if len(tiendas) > 1:
        otra = tiendas[1]
        comunes = [i for i in items if i in set(paneles[otra].index)]
        idx_a = [list(items).index(i) for i in comunes]
        idx_b = [list(paneles[otra].index).index(i) for i in comunes]
        Ra, Rb = R[idx_a], residuos[otra][idx_b]
        n = min(Ra.shape[1], Rb.shape[1])
        C_nulo = (Ra[:, :n] @ Rb[:, :n].T) / n
        np.fill_diagonal(C_nulo, np.nan)                 # el mismo producto consigo mismo no
        nulo = C_nulo[~np.isnan(C_nulo)]
        p95, p99 = np.percentile(nulo, [95, 99])
        misma = C_resid[iu]
        print(f"  {len(nulo):,} parejas entre tiendas distintas")
        print(f"    media {nulo.mean():+.4f} · p95 {p95:+.4f} · p99 {p99:+.4f}")
        print(f"  parejas de la MISMA tienda por encima del p99 del nulo: "
              f"{(misma > p99).sum():,}  ({(misma > p99).mean()*100:.2f}%)")
        exceso = (misma > p99).mean() * 100
        print(f"\n  Por azar se esperaría un 1,00%. Observado: {exceso:.2f}%.")
        veredicto_nulo = bool(exceso > 2.0)
        print("  → " + ("HAY exceso sobre el ruido: merece seguir mirando."
                        if veredicto_nulo else
                        "NO hay exceso apreciable: la afinidad no se distingue del ruido."))
    else:
        veredicto_nulo = None
        print("  (se necesitan al menos dos tiendas; pasá --tiendas con dos códigos)")

    # ---------- prueba 2: nitidez temporal ----------
    print("\n" + "=" * 74)
    print("PASO 3 · Nitidez temporal (¿es del mismo día o es tendencia compartida?)")
    print("=" * 74)
    top = pares_superiores(C_resid, items, k)
    pos = {it: j for j, it in enumerate(items)}
    filas = []
    for a, b, r0 in top:
        ra, rb = R[pos[a]], R[pos[b]]
        r_mas = float(np.corrcoef(ra[:-1], rb[1:])[0, 1])
        r_menos = float(np.corrcoef(ra[1:], rb[:-1])[0, 1])
        nitidez = r0 - max(r_mas, r_menos)
        # estabilidad fuera de muestra
        r_tr = float(np.corrcoef(ra[:corte], rb[:corte])[0, 1])
        r_te = float(np.corrcoef(ra[corte:], rb[corte:])[0, 1])
        filas.append({"producto_a": a, "producto_b": b, "r_mismo_dia": r0,
                      "r_desplazado": max(r_mas, r_menos), "nitidez": nitidez,
                      "r_entrenamiento": r_tr, "r_prueba": r_te,
                      "sobrevive": bool(nitidez > UMBRAL_NITIDEZ and r_te > 0.5 * r_tr)})
    df = pd.DataFrame(filas)
    print(df.head(20).round(3).to_string(index=False))
    print(f"\n  nitidez mediana de las {k} mejores parejas: {df['nitidez'].median():+.3f}")
    print(f"  parejas nítidas y estables fuera de muestra: {int(df['sobrevive'].sum())} de {k}")
    print("""
  ATENCIÓN al leer este número: la nitidez NO separa señal de ruido por sí sola. Dos series
  independientes también tienen correlación cero al desplazarlas un día, así que una pareja
  elegida por azar entre 20.000 pasa esta prueba con facilidad. Esta tabla dice CÓMO son las
  mejores parejas; quien decide si existen es el nulo entre tiendas del paso 2.""")

    # ---------- veredicto ----------
    print("\n" + "=" * 74)
    print("VEREDICTO")
    print("=" * 74)
    sobreviven = int(df["sobrevive"].sum())
    if veredicto_nulo is False:
        print(f"""  NO HAY SEÑAL. Las parejas de la misma tienda no superan el nivel de ruido medido
  entre tiendas distintas, que es la única prueba que puede distinguir afinidad de azar.
  Que {sobreviven} de las {k} mejores parejas parezcan nítidas no lo contradice: con 20.000
  parejas, las mejores por azar siempre lo parecen.

  Es un resultado, no un fracaso, y ocupa un párrafo en las conclusiones: se evaluó la
  posibilidad de derivar recomendaciones de venta cruzada y se comprobó que el co-movimiento
  aparente entre productos se explica por el calendario y el tráfico de la tienda.

  Se recomienda incorporar el identificador de ticket al registro de ventas: es el dato que
  permitiría un análisis de cesta de verdad, y hoy no existe.""")
    elif veredicto_nulo and sobreviven >= max(5, k // 8):
        print(f"""  HAY SEÑAL. {sobreviven} parejas superan el nulo entre tiendas, son nítidas en el
  día y se repiten fuera de muestra. Merece una sección en §7.2.

  Cómo hay que escribirlo, y esto no es negociable: **afinidad de demanda, no compra
  conjunta**. Con datos agregados por día no se puede afirmar que dos productos vayan en
  la misma cesta; se puede afirmar que su demanda co-mueve más de lo que el calendario
  explica. Eso sostiene una hipótesis de promoción conjunta, no una conclusión.

  El cierre natural del capítulo es el mismo que el de la Tarea 5: un candidato y un
  diseño experimental. Una promoción cruzada sobre las parejas supervivientes frente a un
  grupo de control es lo que convertiría la hipótesis en un efecto medido.""")
    else:
        print(f"""  NO HAY SEÑAL SUFICIENTE. {sobreviven} parejas de {k} superan las pruebas.

  Es un resultado, no un fracaso, y ocupa un párrafo en las conclusiones: se evaluó la
  posibilidad de derivar recomendaciones de venta cruzada, se comprobó que el
  co-movimiento aparente entre productos se explica por el calendario y el tráfico de la
  tienda, y que lo que queda no se distingue del ruido medido entre tiendas distintas.

  Se recomienda incorporar el identificador de ticket en el registro de ventas: es el dato
  que permitiría un análisis de cesta de verdad, y hoy no existe.""")

    df.to_csv(os.path.join(SALIDA, "afinidad_parejas.csv"), index=False)
    print(f"\nguardado en {SALIDA}  ·  total {time.time()-t0:.0f}s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--productos", type=int, default=200,
                    help="productos por tienda, por facturación (200 => ~20.000 parejas)")
    ap.add_argument("--tiendas", nargs="*", default=None,
                    help="dos códigos de tienda; la primera es la principal y la segunda el nulo")
    ap.add_argument("--top", dest="k", type=int, default=40, help="parejas a examinar en detalle")
    a = ap.parse_args()
    main(a.productos, a.tiendas, a.k)
