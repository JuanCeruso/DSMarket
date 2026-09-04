# -*- coding: utf-8 -*-
"""
Reparación puntual: cruce de cuantiles en fact_predicciones.

QUÉ PASÓ
--------
El contrato «el p90 no está por debajo de la media» encontró **25.296 filas de 853.720 (2,96%)**
donde la predicción del percentil 90 es menor que la predicción de la media. Eso es imposible por
definición: el percentil 90 de una distribución no puede estar por debajo de su media prevista si
ambas describen la misma demanda.

La causa es que los dos modelos se entrenan por separado —uno con pérdida Tweedie y otro con
pérdida pinball— y nada les obliga a ser monótonos entre sí. En series de demanda casi nula la
media de Tweedie puede quedar por encima del cuantil estimado. Es un fenómeno conocido como
*cruce de cuantiles*.

POR QUÉ IMPORTA MÁS DE LO QUE PARECE
------------------------------------
La política de reposición calcula el stock de seguridad a partir de (p90 − media), recortado a
cero cuando sale negativo. Es decir: **en cada fila cruzada la serie se queda sin stock de
seguridad**. Y el problema no está repartido al azar:

    CZ  10,90%  de sus predicciones cruzadas
    BZ   0,78%
    AZ   0,38%
    AX   0,00%

Se concentra casi por completo en la clase Z, que es **la de demanda errática**: exactamente las
series que más necesitan un colchón son las que se estaban quedando sin él. El efecto es pequeño
en unidades —el hueco medio es de 0,044 y el máximo de 6,77— pero es sistemático y va en la peor
dirección posible.

LA REPARACIÓN
-------------
Dos partes. Esta es la primera:

  1. **Este script** corrige el fichero actual imponiendo p90 = max(p90, media).
  2. **`operacion/predecir.py` ya lo evita** de origen: aplica la misma monotonía al escribir.

    python3 parches/arreglar_cruce_cuantiles.py            # informa y repara
    python3 parches/arreglar_cruce_cuantiles.py --revisar  # solo informa
"""
from __future__ import annotations
import argparse, os, sys
import duckdb

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLD = os.path.join(RAIZ, "lakehouse", "gold")
FICHERO = os.path.join(GOLD, "fact_predicciones.parquet")


def main(revisar):
    if not os.path.exists(FICHERO):
        sys.exit(f"No encuentro {FICHERO}. Ejecutá este parche desde la carpeta PROYECTO/.")

    con = duckdb.connect()
    con.execute(f"SET memory_limit='{os.environ.get('DSMARKET_MEM', '2GB')}';")
    tmpdir = os.path.join(os.path.expanduser("~"), ".duckdb_tmp")
    os.makedirs(tmpdir, exist_ok=True)
    con.execute(f"SET temp_directory='{tmpdir}';")
    con.execute(f"CREATE VIEW p AS SELECT * FROM read_parquet('{FICHERO}')")

    total, cruz, hueco, peor = con.execute("""
        SELECT count(*),
               sum(CASE WHEN prediccion_p90 < prediccion_media THEN 1 ELSE 0 END),
               avg(CASE WHEN prediccion_p90 < prediccion_media
                        THEN prediccion_media - prediccion_p90 END),
               max(CASE WHEN prediccion_p90 < prediccion_media
                        THEN prediccion_media - prediccion_p90 END)
        FROM p
    """).fetchone()
    cruz = int(cruz or 0)

    print(f"\n  filas totales      : {total:,}")
    print(f"  filas cruzadas     : {cruz:,}  ({cruz / max(total,1) * 100:.2f}%)")
    if cruz:
        print(f"  hueco medio        : {hueco:.4f} unidades")
        print(f"  hueco máximo       : {peor:.4f} unidades")

        seg = os.path.join(GOLD, "dim_serie.parquet")
        if os.path.exists(seg):
            con.execute(f"CREATE VIEW s AS SELECT * FROM read_parquet('{seg}')")
            print("\n  por segmento:")
            print(con.execute("""
                SELECT s.clase_abc || s.clase_xyz AS segmento, count(*) AS filas,
                       round(100.0 * sum(CASE WHEN p.prediccion_p90 < p.prediccion_media
                                              THEN 1 ELSE 0 END) / count(*), 2) AS pct_cruzadas
                FROM p JOIN s USING (item, store_code)
                GROUP BY 1 HAVING pct_cruzadas > 0 ORDER BY 3 DESC
            """).df().to_string(index=False))

    if cruz == 0:
        print("\n  No hay nada que reparar.")
        con.close(); return
    if revisar:
        print("\n  (--revisar: no se ha modificado nada)")
        con.close(); return

    copia = FICHERO.replace(".parquet", "_antes_del_arreglo.parquet")
    if not os.path.exists(copia):
        con.execute(f"COPY p TO '{copia}' (FORMAT PARQUET)")
        print(f"\n  copia de seguridad: {os.path.basename(copia)}")

    tmp = FICHERO + ".tmp"
    con.execute(f"""
        COPY (SELECT * REPLACE (greatest(prediccion_p90, prediccion_media) AS prediccion_p90)
              FROM p) TO '{tmp}' (FORMAT PARQUET)
    """)
    con.close()
    os.replace(tmp, FICHERO)

    con = duckdb.connect()
    resto = con.execute(f"""
        SELECT sum(CASE WHEN prediccion_p90 < prediccion_media THEN 1 ELSE 0 END)
        FROM read_parquet('{FICHERO}')
    """).fetchone()[0]
    con.close()
    print(f"  reparado · filas cruzadas restantes: {int(resto or 0)}")
    print("""
  Recalculá después los niveles objetivo, que dependen de (p90 − media):

      python3 operacion/reposicion.py

  Y para que no vuelva a pasar, la predicción se genera ya con la monotonía impuesta:
  operacion/predecir.py aplica max(p90, media) antes de escribir.""")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--revisar", action="store_true", help="informar sin modificar")
    a = ap.parse_args()
    main(a.revisar)
