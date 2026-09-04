# -*- coding: utf-8 -*-
"""
Experimento 7 — Cuánta demanda no vemos: acotar la censura por rotura de stock.

EL PROBLEMA
-----------
`fact_ventas` registra unidades **vendidas**, no demandadas. Si una tienda se quedó sin stock,
ese día aparece un cero, y ese cero no significa que nadie quisiera el producto. Es **demanda
censurada**, y hoy todo el proyecto la trata como demanda real.

Las consecuencias son concretas:

  · El modelo se entrena con demanda censurada, así que **predice por debajo** de la demanda
    verdadera. El sesgo es peor justo donde más rotura hay, que es donde más falta acertar.
  · La simulación de la Tarea 4 calcula el faltante como max(D − S, 0) con D = ventas
    observadas. Pero esas ventas **ya excluyen** lo que se perdió por rotura. Los 161.353 USD de
    margen perdido son una **cota inferior**, no una estimación.

Sin datos de inventario esto no se puede corregir, solo **acotar**. Eso es exactamente lo que
hace este script, y el resultado refuerza la conclusión del proyecto en vez de romperla: si ya
con la medición conservadora se pierden catorce dólares por cada uno inmovilizado, la realidad
es peor.

CÓMO SE ACOTA
-------------
Un cero puede ser demanda cero (lo normal en la cola larga) o una rotura. Se separan por
probabilidad: bajo un modelo Poisson con la intensidad esperada de ese día —media móvil de 28
días corregida por día de la semana—, la probabilidad de observar cero es exp(−lambda). Un cero
con lambda alta es sospechoso.

    cota inferior : solo los ceros con P(cero) < 5%, contados como demanda perdida = lambda
    cota superior : todos los ceros, ponderados por (1 − P(cero))

LA PRUEBA QUE DECIDE SI ESTO ES SEÑAL O RUIDO
---------------------------------------------
**Una rotura dura días; el ruido de Poisson no.** Si los ceros sospechosos fueran solo azar,
aparecerían aislados y su longitud de racha seguiría la distribución geométrica que predice el
propio modelo Poisson. Si son roturas, se agrupan en rachas más largas de lo esperable.

El script compara la distribución observada de longitudes de racha con la esperada bajo
independencia. Si no hay exceso de rachas largas, no hay evidencia de censura y hay que decirlo.

    python3 avanzado/07_censura_cota.py
    python3 avanzado/07_censura_cota.py --margen 0.25 --umbral 0.05
"""
import argparse, os, sys, time
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comun import cargar_matrices, conectar, SALIDA

VENTANA = 28


def intensidad_esperada(V, cal):
    """lambda_{i,t}: media móvil de 28 días corregida por el perfil de día de la semana."""
    n_series, n_dias = V.shape
    Vf = V.astype(np.float32)
    cs = np.zeros((n_series, n_dias + 1), np.float32)
    np.cumsum(Vf, axis=1, dtype=np.float32, out=cs[:, 1:])
    base = np.zeros_like(Vf)
    for t in range(VENTANA, n_dias):
        base[:, t] = (cs[:, t] - cs[:, t - VENTANA]) / VENTANA
    wd = pd.to_datetime(cal["fecha"]).dt.weekday.to_numpy()
    total = Vf.sum(axis=0)
    perfil = np.array([total[(wd == d) & (total > 0)].mean() for d in range(7)])
    perfil = perfil / perfil.mean()
    lam = base * perfil[wd][None, :]
    lam[:, :VENTANA] = np.nan                       # sin ventana suficiente
    return lam


def rachas(mask_fila):
    """Longitudes de las rachas de True en un vector booleano."""
    if not mask_fila.any():
        return []
    d = np.diff(np.concatenate(([0], mask_fila.view(np.int8), [0])))
    ini = np.flatnonzero(d == 1)
    fin = np.flatnonzero(d == -1)
    return (fin - ini).tolist()


def main(margen, umbral, max_series):
    t0 = time.time()
    print("cargando el almacén…", flush=True)
    V, P, cs, cal, meta = cargar_matrices()
    n_series, n_dias = V.shape
    print(f"  {n_series:,} series x {n_dias:,} días  [{time.time()-t0:.0f}s]", flush=True)

    lam = intensidad_esperada(V, cal)
    valido = ~np.isnan(lam) & ~np.isnan(P)             # dias con precio y con ventana
    es_cero = (V == 0) & valido
    p_cero = np.exp(-np.clip(lam, 0, 50))

    sospechoso = es_cero & (p_cero < umbral)
    print(f"\n  días válidos            : {valido.sum():,}")
    print(f"  días con venta cero     : {es_cero.sum():,}  ({es_cero.sum()/valido.sum()*100:.1f}%)")
    print(f"  ceros sospechosos       : {sospechoso.sum():,}  "
          f"({sospechoso.sum()/max(es_cero.sum(),1)*100:.1f}% de los ceros)")

    # ---------- la prueba: ¿se agrupan en rachas? ----------
    print("\n" + "=" * 74)
    print("PRUEBA · ¿Los ceros sospechosos se agrupan como una rotura, o son ruido?")
    print("=" * 74)
    rng = np.random.default_rng(42)
    idx = np.flatnonzero(sospechoso.any(axis=1))
    if len(idx) > max_series:
        idx = rng.choice(idx, max_series, replace=False)

    obs, esp = [], []
    for k in idx:
        obs += rachas(sospechoso[k])
        # nulo: mismos días válidos, ceros independientes con la misma probabilidad diaria
        v = valido[k]
        p = sospechoso[k][v].mean()
        sim = rng.random(v.sum()) < p
        fila = np.zeros(n_dias, bool); fila[v] = sim
        esp += rachas(fila)
    obs, esp = np.array(obs), np.array(esp)
    if len(obs) == 0:
        print("  no hay ceros sospechosos: no hay censura detectable.")
        return

    tabla = []
    for L in [1, 2, 3, 4, 5]:
        o = (obs >= L).sum() / len(obs) * 100
        e = (esp >= L).sum() / max(len(esp), 1) * 100
        tabla.append({"longitud_racha": f">= {L} días", "observado_%": round(o, 2),
                      "esperado_si_azar_%": round(e, 2),
                      "exceso": round(o - e, 2)})
    print(pd.DataFrame(tabla).to_string(index=False))
    exceso3 = (obs >= 3).sum() / len(obs) * 100 - (esp >= 3).sum() / max(len(esp), 1) * 100
    hay_censura = exceso3 > 3.0
    print(f"\n  media de la racha observada {obs.mean():.2f} días  ·  simulada {esp.mean():.2f}")
    print("  → " + ("HAY exceso de rachas largas: es compatible con rotura de stock, no con ruido."
                    if hay_censura else
                    "NO hay exceso de rachas largas: los ceros son compatibles con demanda nula."))

    # ---------- las dos cotas ----------
    print("\n" + "=" * 74)
    print("COTAS DE LA DEMANDA NO OBSERVADA")
    print("=" * 74)
    precio = np.nan_to_num(P, nan=0.0)
    perdida_inf = np.where(sospechoso, lam, 0.0)
    perdida_sup = np.where(es_cero, np.nan_to_num(lam) * (1 - p_cero), 0.0)

    u_obs = float(V[valido].sum())
    filas = []
    for nombre, perd in [("cota inferior (solo ceros sospechosos)", perdida_inf),
                         ("cota superior (todos los ceros ponderados)", perdida_sup)]:
        u = float(np.nan_to_num(perd).sum())
        d = float((np.nan_to_num(perd) * precio).sum())
        filas.append({"escenario": nombre, "unidades_no_vistas": u,
                      "% sobre lo vendido": u / u_obs * 100,
                      "margen_perdido_USD": d * margen})
    res = pd.DataFrame(filas)
    print(f"  unidades vendidas registradas: {u_obs:,.0f}\n")
    print(res.round(1).to_string(index=False))

    # ---------- traducción al periodo de la Tarea 4 ----------
    ini = n_dias - 28
    v28 = valido[:, ini:]
    inf28 = float(np.nan_to_num(perdida_inf[:, ini:])[v28].sum())
    sup28 = float(np.nan_to_num(perdida_sup[:, ini:])[v28].sum())
    pr28 = precio[:, ini:]
    d_inf = float((np.nan_to_num(perdida_inf[:, ini:]) * pr28).sum()) * margen
    d_sup = float((np.nan_to_num(perdida_sup[:, ini:]) * pr28).sum()) * margen

    print("\n" + "=" * 74)
    print("QUÉ LE HACE ESTO A LA CIFRA DE LA TAREA 4")
    print("=" * 74)
    print(f"""  Margen perdido medido en la simulación (28 días) : 161.353 USD
  Margen que la censura oculta, cota inferior      : {d_inf:>10,.0f} USD
  Margen que la censura oculta, cota superior      : {d_sup:>10,.0f} USD
  ------------------------------------------------------------------
  Coste real de la rotura, entre                   : {161353+d_inf:>10,.0f} y {161353+d_sup:,.0f} USD

  Frente a los 11.527 USD de coste de mantenimiento, la proporción de catorce a uno pasa a
  estar entre {(161353+d_inf)/11527:.0f} y {(161353+d_sup)/11527:.0f} a uno.""")

    # ---------- por segmento ----------
    con = conectar()
    seg = con.execute("SELECT item, store_code, clase_abc, clase_xyz FROM dim_serie").df()
    con.close()
    clave = {(i, s): k for k, (i, s) in enumerate(zip(meta["item"], meta["store_code"]))}
    seg["fila"] = [clave.get((i, s), -1) for i, s in zip(seg["item"], seg["store_code"])]
    seg = seg[seg["fila"] >= 0]
    seg["celda"] = seg["clase_abc"] + seg["clase_xyz"]
    por_seg = []
    for celda, g in seg.groupby("celda"):
        f = g["fila"].to_numpy()
        vendidas = float(V[f][valido[f]].sum())
        ocultas = float(np.nan_to_num(perdida_inf[f]).sum())
        por_seg.append({"segmento": celda, "series": len(f), "unidades_vendidas": vendidas,
                        "ocultas_cota_inf": ocultas,
                        "% oculto": ocultas / max(vendidas, 1) * 100})
    seg_df = pd.DataFrame(por_seg).sort_values("% oculto", ascending=False)
    print("\n=== DÓNDE SE CONCENTRA LA CENSURA ===")
    print(seg_df.round(2).to_string(index=False))

    res.to_csv(os.path.join(SALIDA, "censura_cotas.csv"), index=False)
    seg_df.to_csv(os.path.join(SALIDA, "censura_por_segmento.csv"), index=False)
    pd.DataFrame(tabla).to_csv(os.path.join(SALIDA, "censura_rachas.csv"), index=False)

    print(f"""
CÓMO ESCRIBIRLO EN LA MEMORIA
-----------------------------
Esto no es una corrección, es una **cota**, y hay que presentarlo así. Sin datos de inventario
no se puede saber qué ceros fueron rotura; sí se puede decir cuántos son incompatibles con
demanda nula y acotar lo que ocultan.

Las tres frases que valen:

  1. «Las ventas no son la demanda: un cero puede ser ausencia de demanda o ausencia de
     producto, y con estos datos no se distinguen.»
  2. «El sesgo tiene dirección conocida: el modelo predice por debajo y la simulación
     infravalora el coste de la rotura. Nuestras cifras son conservadoras.»
  3. «El dato que cerraría esta incertidumbre es el inventario diario por tienda, y es la
     segunda recomendación de este trabajo después de medir la merma.»

Y en §7.7.3, la limitación pasa de la posición 1 —"no se dispone del inventario real"— a
llevar su magnitud acotada, que es bastante más sólido.

guardado en {SALIDA}  ·  total {time.time()-t0:.0f}s""")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--margen", type=float, default=0.25, help="margen bruto sobre el precio")
    ap.add_argument("--umbral", type=float, default=0.05,
                    help="P(cero) por debajo de la cual un cero se considera sospechoso")
    ap.add_argument("--series", dest="max_series", type=int, default=4000,
                    help="series para la prueba de rachas")
    a = ap.parse_args()
    main(a.margen, a.umbral, a.max_series)
