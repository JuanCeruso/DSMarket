# -*- coding: utf-8 -*-
"""
Contratos de datos: comprobaciones que **rompen el pipeline**.

La diferencia entre una comprobación de calidad y un contrato es qué pasa cuando falla. Una
comprobación avisa; un contrato detiene la ejecución. Un almacén que publica datos rotos porque
la comprobación solo escribió una advertencia en un registro que nadie lee es peor que uno que
no comprueba nada, porque da una falsa sensación de control.

Cada contrato declara su severidad:
    BLOQUEA  el pipeline se detiene y no se publica nada
    AVISA    se registra y se continúa

    python3 operacion/contratos.py             # comprueba y devuelve código de salida
    python3 operacion/contratos.py --detalle   # muestra también los que pasan
"""
from __future__ import annotations
import argparse, sys
from base import conectar, anexar, ahora, nuevo_id

BLOQUEA, AVISA = "BLOQUEA", "AVISA"

# Cada contrato: (nombre, severidad, sql que devuelve UNA fila con la columna 'malas', descripción)
CONTRATOS = [
    ("dim_serie completa", BLOQUEA,
     "SELECT 30490 - count(*) AS malas FROM dim_serie",
     "El panel producto-tienda debe estar completo: 3.049 x 10."),

    ("sin ventas sin precio", BLOQUEA,
     "SELECT count(*) AS malas FROM fact_ventas WHERE precio IS NULL AND unidades > 0",
     "Una venta sin precio indica que el cruce con el histórico de precios falló."),

    ("unidades no negativas", BLOQUEA,
     "SELECT count(*) AS malas FROM fact_ventas WHERE unidades < 0",
     "Una devolución no debe llegar como unidad negativa a la capa de consumo."),

    ("importe coherente", BLOQUEA,
     "SELECT count(*) AS malas FROM fact_ventas "
     "WHERE precio IS NOT NULL AND abs(importe - unidades * precio) > 0.01",
     "El importe debe ser el producto de unidades por precio."),

    ("integridad referencial de producto", BLOQUEA,
     "SELECT count(*) AS malas FROM (SELECT DISTINCT item FROM fact_ventas) v "
     "LEFT JOIN dim_producto p USING (item) WHERE p.item IS NULL",
     "Toda referencia vendida debe existir en la dimensión de producto."),

    ("integridad referencial de tienda", BLOQUEA,
     "SELECT count(*) AS malas FROM (SELECT DISTINCT store_code FROM fact_ventas) v "
     "LEFT JOIN dim_tienda t USING (store_code) WHERE t.store_code IS NULL",
     "Toda tienda vendedora debe existir en la dimensión de tienda."),

    ("calendario cubre el horizonte", BLOQUEA,
     "SELECT CASE WHEN (SELECT max(fecha) FROM dim_calendario) >= "
     "            (SELECT max(fecha) + INTERVAL 28 DAY FROM fact_ventas) THEN 0 ELSE 1 END AS malas",
     "La dimensión de calendario debe llegar 28 días más allá del último día con venta."),

    ("predicciones dentro del calendario", BLOQUEA,
     "SELECT count(*) AS malas FROM fact_predicciones p "
     "LEFT JOIN dim_calendario c USING (fecha) WHERE c.fecha IS NULL",
     "Toda predicción debe apoyarse en una fila de la dimensión temporal."),

    ("predicciones no negativas", BLOQUEA,
     "SELECT count(*) AS malas FROM fact_predicciones "
     "WHERE prediccion_media < 0 OR prediccion_p90 < 0",
     "Una predicción de demanda negativa no tiene interpretación."),

    ("el p90 no está por debajo de la media", BLOQUEA,
     "SELECT count(*) AS malas FROM fact_predicciones WHERE prediccion_p90 < prediccion_media",
     "Un percentil 90 por debajo de la media indica cruce de cuantiles."),

    ("frescura de los datos", AVISA,
     "SELECT CASE WHEN (SELECT max(fecha) FROM fact_ventas) < current_date - INTERVAL 45 DAY "
     "            THEN 1 ELSE 0 END AS malas",
     "El último día con venta tiene más de 45 días: el almacén puede estar desactualizado."),

    # Se comprueba sobre el último año en vez de sobre los 58 millones de filas: un duplicado
    # lo introduce una recarga, y una recarga afecta siempre a los datos recientes. Comprobar
    # todo el histórico en cada ejecución cuesta memoria y no aporta.
    ("sin duplicados en el grano", BLOQUEA,
     "SELECT count(*) AS malas FROM (SELECT item, store_code, fecha, count(*) n "
     "FROM fact_ventas WHERE fecha > (SELECT max(fecha) - INTERVAL 365 DAY FROM fact_ventas) "
     "GROUP BY 1,2,3 HAVING n > 1)",
     "El grano de fact_ventas es una fila por producto, tienda y día."),

    # Contrato añadido a raíz de un defecto real: `es_fin_de_semana` marcaba miércoles y jueves.
    # La causa fue suponer que weekday_int era 0=lunes cuando en este calendario es 1=sábado, y
    # nadie se entera porque la columna es booleana y siempre tiene valores plausibles. Un
    # contrato que cruza la bandera con el NOMBRE del día no depende de ninguna convención.
    ("el fin de semana cae en sábado y domingo", BLOQUEA,
     "SELECT count(*) AS malas FROM dim_calendario WHERE dia_semana IS NOT NULL AND "
     "es_fin_de_semana <> (lower(dia_semana) IN ('saturday', 'sunday'))",
     "La bandera de fin de semana debe coincidir con el nombre del día, no con un índice."),

    # El mismo defecto, en su forma peligrosa: que la bandera signifique una cosa en los días con
    # los que se entrena y otra en los días que se predicen. El modelo aprende con una definición
    # y sirve con otra, y el sesgo resultante es invisible y permanente.
    ("la bandera de fin de semana no cambia de significado en el futuro", BLOQUEA,
     "SELECT count(*) AS malas FROM dim_calendario WHERE es_fin_de_semana <> "
     "(dayofweek(fecha) IN (0, 6))",
     "Histórico y horizonte deben usar la misma definición de fin de semana."),

    ("cobertura de segmentación", AVISA,
     "SELECT count(*) AS malas FROM dim_serie WHERE clase_abc IS NULL OR clase_xyz IS NULL",
     "Toda serie debe tener su clasificación ABC/XYZ para que la política pueda aplicarse."),
]


def verificar(detalle: bool = False, ejecucion_id: str | None = None):
    con = conectar()
    resultados, bloqueantes = [], 0
    for nombre, severidad, sql, descripcion in CONTRATOS:
        try:
            malas = int(con.execute(sql).fetchone()[0] or 0)
            estado = "OK" if malas == 0 else severidad
        except Exception as e:
            malas, estado, descripcion = -1, "ERROR", f"{descripcion} | {e}"
        if estado in (BLOQUEA, "ERROR"):
            bloqueantes += 1
        resultados.append({"ejecucion_id": ejecucion_id or "manual", "momento": ahora(),
                           "contrato": nombre, "severidad": severidad, "estado": estado,
                           "filas_malas": malas, "descripcion": descripcion})
    con.close()

    ancho = max(len(r["contrato"]) for r in resultados)
    for r in resultados:
        if r["estado"] == "OK" and not detalle:
            continue
        marca = {"OK": "  ok  ", BLOQUEA: " FALLA", AVISA: " aviso", "ERROR": " ERROR"}[r["estado"]]
        print(f"  [{marca}] {r['contrato']:<{ancho}}  {r['filas_malas']:>10,} filas")
        if r["estado"] != "OK":
            print(f"           {r['descripcion']}")

    anexar("fact_contratos", resultados)
    ok = bloqueantes == 0
    print(f"\n  {len(resultados)} contratos · "
          f"{sum(1 for r in resultados if r['estado']=='OK')} en verde · "
          f"{bloqueantes} bloqueantes")
    return ok, resultados


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--detalle", action="store_true", help="mostrar también los contratos que pasan")
    a = ap.parse_args()
    print("\nCONTRATOS DE DATOS\n" + "-" * 60)
    ok, _ = verificar(a.detalle, nuevo_id("man"))
    sys.exit(0 if ok else 1)
