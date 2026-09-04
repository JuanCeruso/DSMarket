# -*- coding: utf-8 -*-
"""
Experimento 5 — Elegir el modelo por su coste de negocio, no por su error estadístico.

LA IDEA
-------
Hasta ahora el proyecto elige modelo con WRMSSE: una métrica estadística, simétrica y
adimensional. Pero a DSMarket no le cuesta lo mismo pasarse que quedarse corto. Quedarse
corto cuesta el margen de una venta que no ocurrió; pasarse cuesta el mantenimiento del
stock y, si el producto se estropea, la merma. La métrica con la que se elige el modelo
debería ser esa, no el error.

Esto no es una idea suelta: es la misma que ya nos dio el resultado más incómodo del
proyecto. En la Tarea 4 la simulación de la política **invirtió** la conclusión de la
Tarea 3 sobre dónde aporta el modelo. Es decir, ya tenemos un caso probado de que la
métrica de negocio ordena distinto que la métrica de error. Este experimento generaliza
ese hallazgo: en vez de comprobarlo a posteriori sobre un modelo ya elegido, **elige** el
modelo con el criterio de negocio desde el principio.

LA TEORÍA, QUE ES LO QUE HACE ESTO DEFENDIBLE
---------------------------------------------
El coste esperado de un ciclo de reposición es el del vendedor de periódicos:

    C(S) = Cu · E[(D − S)+]  +  Co · E[(S − D)+]

con Cu = coste de quedarse corto (margen unitario perdido) y Co = coste de pasarse
(mantenimiento + merma). Su mínimo está en el cuantil

    τ* = Cu / (Cu + Co)          ← el "ratio crítico"

y —este es el punto— esa función de coste es, salvo una constante multiplicativa,
**la pérdida pinball evaluada en τ***:

    C(S) = (Cu + Co) · L_{τ*}(D − S)

De ahí salen tres consecuencias que ordenan todo el experimento:

  1. Elegir por coste NO es abandonar el rigor estadístico: la métrica de negocio tiene
     un equivalente estadístico exacto. Es la misma función, con el cuantil que la
     economía del producto determina en vez de uno redondo elegido a ojo.
  2. El 90% que usa hoy el proyecto es un número puesto a mano. El ratio crítico dice
     cuál debería ser: con margen 25% y coste de posesión 5%, τ* ≈ 0,83; con un producto
     perecedero de merma 20%, τ* ≈ 0,50. Muy lejos del 0,90 uniforme.
  3. Si la métrica cambia, el modelo ganador puede cambiar. Un modelo que acierta la
     media pero calibra mal la cola pierde con esta métrica aunque gane en MAE.

QUÉ COMPARA EL SCRIPT
---------------------
Cinco candidatos, todos evaluados sobre el mismo fold 3 y los mismos ciclos:

    A  media móvil 28 días + normal        (la referencia que cuesta cero)
    B  LightGBM Tweedie + sigma histórico   (predice la media, la cola la pone dim_serie)
    C  LightGBM Tweedie + sigma de residuos (la cola sale del error observado en fold 2)
    D  LightGBM cuantílico entrenado en tau*  ← el candidato "entrenado para la decisión"
    E  LightGBM cuantílico en 0,90 fijo     (lo que hace hoy el proyecto)

y los ordena por tres criterios: MAE, WRMSSE y **coste total**. Lo interesante del
resultado no es cuál gana sino si los tres ranking coinciden. Si no coinciden, la
memoria tiene un capítulo.

    python3 avanzado/05_seleccion_por_coste.py
    python3 avanzado/05_seleccion_por_coste.py --margen 0.25 --merma 0.10
"""
import argparse, os, sys, time
import numpy as np, pandas as pd
from scipy.stats import norm
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comun import (cargar_matrices, folds, construir_matriz, a_float32, conectar,
                   FEATURES, CATEGORICAS, SALIDA, HORIZONTE, mae, rmse, wrmsse)
import lightgbm as lgb

DIAS_ENTRENAMIENTO = 180
DIAS_REVISION = 7
LEAD_TIME = 2
CICLO = DIAS_REVISION + LEAD_TIME            # 9 dias de cobertura por pedido
N_CICLOS = HORIZONTE // CICLO                # 3 ciclos completos dentro del fold

PARAMS_BASE = dict(metric="rmse", learning_rate=0.05, num_leaves=96, min_data_in_leaf=100,
                   feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1,
                   num_threads=4, verbose=-1, seed=42, max_bin=127)


# --------------------------------------------------------------------------- utilidades
def ratio_critico(margen, mantenimiento, merma):
    """tau* = Cu / (Cu + Co).  Todo en fraccion del precio de venta."""
    cu = margen
    co = mantenimiento + merma
    return float(cu / (cu + co))


def entrenar_bloques(ini, V, P, cs, cal, meta, params, alpha=None):
    """Los 4 modelos semanales del proyecto. Devuelve matriz (series x 28) de predicciones."""
    n_series = V.shape[0]
    salida = np.zeros((n_series, HORIZONTE), np.float32)
    p = dict(params)
    if alpha is not None:
        p.update(objective="quantile", alpha=alpha, metric="quantile")
    for bloque in range(4):
        min_lag = 7 * (bloque + 1)
        Xtr = construir_matriz(range(ini - DIAS_ENTRENAMIENTO, ini - 28), V, P, cs, cal, meta, min_lag)
        Xva = construir_matriz(range(ini - 28, ini), V, P, cs, cal, meta, min_lag)
        d1 = lgb.Dataset(a_float32(Xtr), label=Xtr["y"].to_numpy(np.float32),
                         feature_name=FEATURES, categorical_feature=CATEGORICAS)
        d2 = lgb.Dataset(a_float32(Xva), label=Xva["y"].to_numpy(np.float32), reference=d1)
        m = lgb.train(p, d1, num_boost_round=800, valid_sets=[d2],
                      callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)])
        dias = range(ini + 7 * bloque, min(ini + 7 * (bloque + 1), ini + HORIZONTE))
        Xte = construir_matriz(dias, V, P, cs, cal, meta, min_lag)
        salida[Xte["serie"].values, Xte["dia"].values - ini] = np.maximum(
            m.predict(a_float32(Xte), num_iteration=m.best_iteration), 0)
        del Xtr, Xva, Xte, d1, d2, m
    return salida


def por_ciclos(mat):
    """(series x 28) -> (series x N_CICLOS): suma de cada ventana de 9 dias."""
    util = mat[:, :N_CICLOS * CICLO]
    return util.reshape(mat.shape[0], N_CICLOS, CICLO).sum(axis=2)


def coste(S, D, precio_ciclo, margen, mantenimiento, merma):
    """Coste newsvendor por ciclo, en dolares. S = nivel objetivo, D = demanda real."""
    faltante = np.maximum(D - S, 0.0)
    remanente = np.maximum(S - D, 0.0)
    perdido = faltante * precio_ciclo * margen
    posesion = remanente * precio_ciclo * mantenimiento
    descarte = remanente * precio_ciclo * merma
    return perdido, posesion, descarte


# --------------------------------------------------------------------------- principal
def main(margen, mantenimiento, merma, rejilla):
    t0 = time.time()
    print("cargando el almacén…", flush=True)
    V, P, cs, cal, meta = cargar_matrices()
    n_dias = V.shape[1]
    (ini_prev, _), (ini, fin) = folds(n_dias)[1], folds(n_dias)[2]

    tau = ratio_critico(margen, mantenimiento, merma)
    print(f"\nsupuestos: margen {margen:.0%} · mantenimiento {mantenimiento:.0%} · merma {merma:.0%}")
    print(f"ratio crítico tau* = {tau:.3f}   (el proyecto usa 0,90 fijo)\n", flush=True)

    # ---------- datos de la serie que necesita la política ----------
    con = conectar()
    ser = con.execute("""SELECT item, store_code, media_dia, desvio_dia,
                                clase_abc, clase_xyz, facturacion_90d
                         FROM dim_serie""").df()
    con.close()
    clave = {(i, s): k for k, (i, s) in enumerate(zip(meta["item"], meta["store_code"]))}
    ser["fila"] = [clave.get((i, s), -1) for i, s in zip(ser["item"], ser["store_code"])]
    ser = ser[ser["fila"] >= 0].sort_values("fila").reset_index(drop=True)
    orden = ser["fila"].to_numpy()

    sigma_hist = (ser["desvio_dia"].to_numpy(np.float32) * np.sqrt(CICLO))
    media_hist = ser["media_dia"].to_numpy(np.float32)
    segmento = (ser["clase_abc"] + ser["clase_xyz"]).to_numpy()

    # ---------- demanda real y precio del fold ----------
    D_real = por_ciclos(V[:, ini:fin].astype(np.float32))[orden]
    precio = np.nan_to_num(P[:, ini:fin], nan=0.0)
    precio_ciclo = por_ciclos(precio)[orden] / CICLO          # precio medio del ciclo
    validas = (precio_ciclo > 0).all(axis=1)

    # ---------- candidatos ----------
    print("A · media móvil de 28 días", flush=True)
    mm = (cs[:, ini] - cs[:, ini - 28]) / 28.0
    pred_mm_dia = np.repeat(mm[:, None], HORIZONTE, axis=1)

    print("B/C · LightGBM Tweedie", flush=True)
    p_tw = dict(PARAMS_BASE, objective="tweedie", tweedie_variance_power=1.1)
    pred_tw_dia = entrenar_bloques(ini, V, P, cs, cal, meta, p_tw)

    print("   · residuos del fold anterior (para el sigma del candidato C)", flush=True)
    pred_tw_prev = entrenar_bloques(ini_prev, V, P, cs, cal, meta, p_tw)
    resid = por_ciclos(V[:, ini_prev:ini_prev + HORIZONTE].astype(np.float32)) - por_ciclos(pred_tw_prev)
    sigma_resid = resid.std(axis=1)[orden]
    del pred_tw_prev, resid

    print(f"D · LightGBM cuantílico en tau* = {tau:.3f}", flush=True)
    pred_q_tau_dia = entrenar_bloques(ini, V, P, cs, cal, meta, PARAMS_BASE, alpha=tau)

    print("E · LightGBM cuantílico en 0,90", flush=True)
    pred_q90_dia = entrenar_bloques(ini, V, P, cs, cal, meta, PARAMS_BASE, alpha=0.90)

    # ---------- niveles objetivo por candidato ----------
    z = norm.ppf(tau)
    mu_mm = por_ciclos(pred_mm_dia)[orden]
    mu_tw = por_ciclos(pred_tw_dia)[orden]

    candidatos = {
        "A · media móvil + normal":        mu_mm + z * sigma_hist[:, None],
        "B · LightGBM + sigma histórico":  mu_tw + z * sigma_hist[:, None],
        "C · LightGBM + sigma residual":   mu_tw + z * sigma_resid[:, None],
        "D · cuantílico en tau*":          por_ciclos(pred_q_tau_dia)[orden],
        "E · cuantílico en 0,90":          por_ciclos(pred_q90_dia)[orden],
    }
    medias_diarias = {                      # para las métricas de error, que miran la media
        "A · media móvil + normal":        pred_mm_dia,
        "B · LightGBM + sigma histórico":  pred_tw_dia,
        "C · LightGBM + sigma residual":   pred_tw_dia,
        "D · cuantílico en tau*":          pred_q_tau_dia,
        "E · cuantílico en 0,90":          pred_q90_dia,
    }

    # ---------- evaluación ----------
    y_dia = V[:, ini:fin].astype(np.float32)
    V_tr = V[:, ini - 365:ini].astype(np.float32)
    P_tr = np.nan_to_num(P[:, ini - 365:ini], nan=0.0)

    filas = []
    for nombre, S in candidatos.items():
        S = np.maximum(S, 0.0)
        perdido, posesion, descarte = coste(S[validas], D_real[validas], precio_ciclo[validas],
                                            margen, mantenimiento, merma)
        total = perdido.sum() + posesion.sum() + descarte.sum()
        atendida = np.minimum(S[validas], D_real[validas]).sum()
        servicio = atendida / max(D_real[validas].sum(), 1)
        pm = medias_diarias[nombre]
        filas.append({
            "candidato": nombre,
            "MAE": mae(y_dia, pm),
            "WRMSSE": wrmsse(y_dia, pm, V_tr, P_tr),
            "coste_USD": float(total),
            "margen_perdido": float(perdido.sum()),
            "mantenimiento": float(posesion.sum()),
            "merma": float(descarte.sum()),
            "servicio_%": float(servicio * 100),
        })
    res = pd.DataFrame(filas)

    print("\n" + "=" * 78)
    print("COMPARACIÓN · fold 3 · 3 ciclos de 9 días")
    print("=" * 78)
    print(res.round(3).to_string(index=False))

    print("\n--- ORDEN SEGÚN CADA CRITERIO ---")
    ordenes = {}
    for crit in ["MAE", "WRMSSE", "coste_USD"]:
        ordenes[crit] = res.sort_values(crit)["candidato"].tolist()
        print(f"{crit:>10}: " + "  >  ".join(c.split(' · ')[0] for c in ordenes[crit]))
    coincide = ordenes["WRMSSE"] == ordenes["coste_USD"]
    print(f"\n¿El ranking por coste coincide con el ranking por WRMSSE?  "
          f"{'SÍ — la métrica estadística basta' if coincide else 'NO — y ahí está el capítulo'}")
    if not coincide:
        mejor_c = res.loc[res['coste_USD'].idxmin(), 'candidato']
        mejor_w = res.loc[res['WRMSSE'].idxmin(), 'candidato']
        ahorro = (res.loc[res['candidato'] == mejor_w, 'coste_USD'].iloc[0]
                  - res['coste_USD'].min())
        print(f"  elegir por WRMSSE habría escogido «{mejor_w}»")
        print(f"  elegir por coste escoge          «{mejor_c}»")
        print(f"  diferencia: {ahorro:,.0f} USD en 27 días sobre las series evaluadas")

    # ---------- por segmento: ¿gana el mismo en todas partes? ----------
    print("\n--- MEJOR CANDIDATO POR SEGMENTO ABC/XYZ ---")
    por_seg = []
    for seg in sorted(set(segmento[validas])):
        m = validas & (segmento == seg)
        if m.sum() < 30:
            continue
        fila = {"segmento": seg, "series": int(m.sum())}
        for nombre, S in candidatos.items():
            pe, po, de = coste(np.maximum(S[m], 0), D_real[m], precio_ciclo[m],
                               margen, mantenimiento, merma)
            fila[nombre.split(' · ')[0]] = float(pe.sum() + po.sum() + de.sum())
        cols = [c for c in fila if c not in ("segmento", "series")]
        fila["gana"] = min(cols, key=lambda c: fila[c])
        por_seg.append(fila)
    seg_df = pd.DataFrame(por_seg)
    print(seg_df.round(0).to_string(index=False))
    n_dist = seg_df["gana"].nunique()
    print(f"\n{n_dist} candidato(s) distinto(s) ganan según el segmento.")
    if n_dist > 1:
        print("  → la conclusión no es «este modelo es el mejor» sino «cada segmento tiene el suyo»,")
        print("    que es exactamente lo que ya sugería la Tarea 4.")

    # ---------- sensibilidad a los supuestos ----------
    if rejilla:
        print("\n--- SENSIBILIDAD: ¿el ganador aguanta otros supuestos? ---")
        rej = []
        for mg in [0.10, 0.25, 0.35]:
            for mr in [0.0, 0.05, 0.10, 0.20]:
                t = ratio_critico(mg, mantenimiento, mr)
                zz = norm.ppf(t)
                cand = {
                    "A": mu_mm + zz * sigma_hist[:, None],
                    "B": mu_tw + zz * sigma_hist[:, None],
                    "C": mu_tw + zz * sigma_resid[:, None],
                    "D": por_ciclos(pred_q_tau_dia)[orden],   # entrenado en el tau* base
                    "E": por_ciclos(pred_q90_dia)[orden],
                }
                cs_ = {}
                for k, S in cand.items():
                    pe, po, de = coste(np.maximum(S[validas], 0), D_real[validas],
                                       precio_ciclo[validas], mg, mantenimiento, mr)
                    cs_[k] = float(pe.sum() + po.sum() + de.sum())
                rej.append({"margen": mg, "merma": mr, "tau*": round(t, 3),
                            "gana": min(cs_, key=cs_.get), **{k: round(v) for k, v in cs_.items()}})
        rej_df = pd.DataFrame(rej)
        print(rej_df.to_string(index=False))
        print(f"\nganadores distintos según supuestos: {sorted(rej_df['gana'].unique())}")
        rej_df.to_csv(os.path.join(SALIDA, "coste_sensibilidad.csv"), index=False)

    res.to_csv(os.path.join(SALIDA, "coste_comparacion.csv"), index=False)
    seg_df.to_csv(os.path.join(SALIDA, "coste_por_segmento.csv"), index=False)
    print(f"\nguardado en {SALIDA}  ·  total {(time.time()-t0)/60:.0f} min")

    print("""
CÓMO LEERLO
-----------
Si los tres ranking coinciden, el resultado es tranquilizador y también publicable: la
métrica estadística es un buen sustituto de la económica en este problema, y elegir por
WRMSSE no cuesta dinero. Dilo así en la memoria.

Si no coinciden —que es lo más probable, porque la Tarea 4 ya invirtió una conclusión de
la Tarea 3— entonces el capítulo se escribe solo: la elección del modelo depende de la
función de pérdida, la función de pérdida correcta es la del negocio, y el proyecto tiene
la simulación para calcularla. Es un argumento de madurez que pocos TFM pueden hacer.

Y mires lo que mires, la tabla de sensibilidad es lo que hay que enseñar en la defensa:
un ganador que cambia con supuestos que nadie ha medido es un ganador frágil, y decirlo
vale más que presentar un número sin intervalo.
""")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--margen", type=float, default=0.25, help="margen bruto sobre el precio")
    ap.add_argument("--mantenimiento", type=float, default=0.05,
                    help="coste de posesión del ciclo, en fracción del precio")
    ap.add_argument("--merma", type=float, default=0.05, help="fracción del remanente que se descarta")
    ap.add_argument("--sin-rejilla", dest="rejilla", action="store_false",
                    help="omitir el análisis de sensibilidad")
    a = ap.parse_args()
    main(a.margen, a.mantenimiento, a.merma, a.rejilla)
