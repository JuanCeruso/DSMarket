# -*- coding: utf-8 -*-
"""
Monitorización: saber cuándo el sistema se está degradando.

Validar un modelo antes de desplegarlo no es monitorizarlo. La validación dice cómo se comportó
sobre datos pasados; la monitorización dice cómo se está comportando **ahora**, y es lo único que
puede avisar de que algo cambió: un cambio de surtido, una tienda nueva, un competidor, una
subida de precios del proveedor.

Se vigilan tres cosas distintas, y conviene no confundirlas:

  1. **Error realizado.** Cuando pasan los días predichos, se compara con lo que ocurrió. Es la
     medida verdadera, y llega tarde por definición: hasta que no pasan 28 días no se sabe.
  2. **Deriva de las variables de entrada.** Se detecta el mismo día, sin esperar al resultado.
     Si la distribución de las variables que alimentan el modelo se aleja de la que vio en el
     entrenamiento, hay motivo para desconfiar antes de saber si acertó.
  3. **Deriva de la predicción.** Si el modelo empieza a predecir sistemáticamente más o menos
     que su propio histórico, algo cambió aunque las entradas parezcan normales.

    python3 operacion/monitor.py
    python3 operacion/monitor.py --umbral-error 1.25 --umbral-psi 0.25
"""
from __future__ import annotations
import argparse
import numpy as np, pandas as pd
from base import conectar, anexar, leer, ahora, nuevo_id

# Umbrales por defecto. No son universales: se calibran con el histórico de la propia serie
# de métricas en cuanto haya unas cuantas ejecuciones.
UMBRAL_ERROR = 1.20      # WRMSSE realizado por encima de este valor -> alerta
UMBRAL_SESGO = 0.15      # desviación relativa del total predicho frente al real
UMBRAL_PSI = 0.20        # índice de estabilidad de población: 0,1 aviso · 0,25 cambio claro


def psi(esperado: np.ndarray, observado: np.ndarray, cortes: int = 10) -> float:
    """Índice de estabilidad de población entre dos muestras de la misma variable.

    Suma sobre deciles de (obs% - esp%) * ln(obs% / esp%). Es simétrico y penaliza tanto que
    una franja se vacíe como que se llene. Convención habitual: <0,1 estable · 0,1-0,25 aviso
    · >0,25 cambio de distribución.
    """
    esperado = esperado[np.isfinite(esperado)]
    observado = observado[np.isfinite(observado)]
    if len(esperado) < 100 or len(observado) < 100:
        return float("nan")
    bordes = np.unique(np.quantile(esperado, np.linspace(0, 1, cortes + 1)))
    if len(bordes) < 3:
        return 0.0
    bordes[0], bordes[-1] = -np.inf, np.inf
    e = np.histogram(esperado, bordes)[0] / len(esperado)
    o = np.histogram(observado, bordes)[0] / len(observado)
    e, o = np.clip(e, 1e-4, None), np.clip(o, 1e-4, None)
    return float(np.sum((o - e) * np.log(o / e)))


def error_realizado(con):
    """Compara las predicciones ya vencidas con lo que ocurrió, por segmento."""
    df = con.execute("""
        SELECT s.clase_abc || s.clase_xyz AS segmento,
               sum(v.unidades)                     AS real_uds,
               sum(p.prediccion_media)             AS pred_uds,
               sum(abs(v.unidades - p.prediccion_media)) AS error_abs,
               sum(CASE WHEN v.unidades <= p.prediccion_p90 THEN 1 ELSE 0 END) AS dentro_p90,
               count(*)                            AS observaciones
        FROM fact_predicciones p
        JOIN fact_ventas v USING (item, store_code, fecha)
        JOIN dim_serie   s USING (item, store_code)
        GROUP BY 1 ORDER BY 1
    """).df()
    if df.empty:
        return df
    df["mae"] = df["error_abs"] / df["observaciones"]
    df["sesgo"] = (df["pred_uds"] - df["real_uds"]) / df["real_uds"].replace(0, np.nan)
    df["cobertura_p90"] = df["dentro_p90"] / df["observaciones"]
    return df


def main(umbral_error, umbral_sesgo, umbral_psi):
    ejecucion = nuevo_id("mon")
    con = conectar()
    print("\nMONITORIZACIÓN\n" + "-" * 68)

    # ---------- 1. error realizado ----------
    print("\n1 · ERROR REALIZADO  (predicciones ya vencidas frente a lo ocurrido)")
    df = error_realizado(con)
    if df.empty:
        print("   todavía no hay predicciones vencidas que comparar.")
    else:
        print(df[["segmento", "observaciones", "mae", "sesgo", "cobertura_p90"]]
              .round(3).to_string(index=False))

    # ---------- 2. deriva de las entradas ----------
    print("\n2 · DERIVA DE LAS VARIABLES DE ENTRADA  (últimos 28 días frente a los 180 previos)")
    ref, act = con.execute("""
        SELECT max(fecha) - INTERVAL 208 DAY, max(fecha) - INTERVAL 28 DAY FROM fact_ventas
    """).fetchone()
    variables = {
        "unidades diarias": ("unidades", "fact_ventas"),
        "precio":           ("precio",   "fact_ventas"),
    }
    filas_psi = []
    for nombre, (col, tabla) in variables.items():
        e = con.execute(f"SELECT {col} x FROM {tabla} WHERE fecha BETWEEN ? AND ? "
                        f"AND {col} IS NOT NULL USING SAMPLE 200000 ROWS",
                        [ref, act]).df()["x"].to_numpy(float)
        o = con.execute(f"SELECT {col} x FROM {tabla} WHERE fecha > ? "
                        f"AND {col} IS NOT NULL USING SAMPLE 200000 ROWS",
                        [act]).df()["x"].to_numpy(float)
        v = psi(e, o)
        estado = "OK" if not np.isfinite(v) or v < 0.10 else ("AVISO" if v < umbral_psi else "ALERTA")
        filas_psi.append({"variable": nombre, "psi": round(v, 4), "estado": estado})
    print(pd.DataFrame(filas_psi).to_string(index=False))
    print("   referencia: <0,10 estable · 0,10-0,25 aviso · >0,25 cambio de distribución")

    # ---------- 3. deriva de la predicción ----------
    print("\n3 · DERIVA DE LA PREDICCIÓN  (frente a las ejecuciones anteriores)")
    hist = leer("fact_metricas")
    actual = con.execute("SELECT avg(prediccion_media) m FROM fact_predicciones").fetchone()[0]
    if hist.empty or "prediccion_media_avg" not in hist:
        print("   primera ejecución registrada: no hay histórico con el que comparar.")
        desvio = 0.0
    else:
        base = hist["prediccion_media_avg"].tail(5).mean()
        desvio = (actual - base) / base if base else 0.0
        print(f"   media predicha ahora {actual:.4f} · media de las últimas 5 ejecuciones "
              f"{base:.4f} · desviación {desvio:+.1%}")

    # ---------- veredicto y registro ----------
    alertas = []
    if not df.empty:
        for _, r in df.iterrows():
            if abs(r["sesgo"]) > umbral_sesgo:
                alertas.append(f"sesgo de {r['sesgo']:+.1%} en el segmento {r['segmento']}")
            if r["cobertura_p90"] < 0.85:
                alertas.append(f"cobertura del p90 en {r['cobertura_p90']:.1%} "
                               f"en el segmento {r['segmento']}")
    alertas += [f"deriva en «{f['variable']}» (PSI {f['psi']})"
                for f in filas_psi if f["estado"] == "ALERTA"]
    if abs(desvio) > umbral_sesgo:
        alertas.append(f"la predicción media se desvió un {desvio:+.1%} de su propio histórico")

    estado = "ALERTA" if alertas else "OK"
    print("\n" + "-" * 68)
    if alertas:
        print(f"ESTADO: ALERTA · {len(alertas)} señales")
        for a in alertas:
            print(f"   · {a}")
        print("\nQué hacer, en este orden: comprobar los contratos de datos, revisar si hubo un\n"
              "cambio de surtido o de tiendas, y solo después reentrenar. Reentrenar sobre datos\n"
              "rotos produce un modelo roto con métricas nuevas.")
    else:
        print("ESTADO: OK · ninguna señal por encima de los umbrales")

    anexar("fact_metricas", [{
        "ejecucion_id": ejecucion, "momento": ahora(), "estado": estado,
        "n_alertas": len(alertas), "alertas": " | ".join(alertas),
        "prediccion_media_avg": float(actual or 0),
        "mae_global": float(df["mae"].mean()) if not df.empty else None,
        "cobertura_p90_global": float(df["cobertura_p90"].mean()) if not df.empty else None,
        **{f"psi_{f['variable'].replace(' ', '_')}": f["psi"] for f in filas_psi},
    }])
    if not df.empty:
        df2 = df.copy(); df2["ejecucion_id"] = ejecucion; df2["momento"] = ahora()
        anexar("fact_metricas_segmento", df2.to_dict("records"))
    con.close()
    print(f"\nregistrado como {ejecucion}")
    return estado == "OK"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--umbral-error", type=float, default=UMBRAL_ERROR)
    ap.add_argument("--umbral-sesgo", type=float, default=UMBRAL_SESGO)
    ap.add_argument("--umbral-psi", type=float, default=UMBRAL_PSI)
    a = ap.parse_args()
    main(a.umbral_error, a.umbral_sesgo, a.umbral_psi)
