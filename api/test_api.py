# -*- coding: utf-8 -*-
"""Pruebas de humo de la API: arranca el servicio en proceso y ejerce los endpoints."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from fastapi.testclient import TestClient
from api.main import app

fallos = []
def comprobar(condicion, mensaje):
    print(("  ok    " if condicion else "  FALLO ") + mensaje)
    if not condicion: fallos.append(mensaje)

with TestClient(app) as cliente:
    print("salud")
    r = cliente.get("/salud")
    comprobar(r.status_code == 200, "responde 200")
    comprobar(r.json()["series_con_prediccion"] == 30490, "carga las 30.490 series")

    print("catálogo")
    comprobar(len(cliente.get("/tiendas").json()) == 10, "devuelve las 10 tiendas")
    seg = cliente.get("/segmentos").json()
    comprobar(abs(sum(s["pct_facturacion"] for s in seg) - 100) < 1.0, "los segmentos suman 100% de facturación")

    print("predicción")
    r = cliente.get("/prediccion/NYC_1/SUPERMARKET_3_069", params={"dias": 7})
    comprobar(len(r.json()["predicciones"]) == 7, "devuelve los días pedidos")
    comprobar(all(p["p90"] >= p["media"] for p in r.json()["predicciones"]), "el p90 nunca es menor que la media")

    print("reposición")
    cuerpo = {"tienda": "NYC_1", "fecha_revision": "2016-04-25",
              "productos": [{"item": "SUPERMARKET_3_511", "stock_actual": 0, "en_transito": 0},
                            {"item": "SUPERMARKET_3_511", "stock_actual": 9999, "en_transito": 0}]}
    s = cliente.post("/reposicion/sugerencia", json=cuerpo).json()["sugerencias"]
    comprobar(s[0]["pedido_sugerido"] > 0, "con stock cero, pide")
    comprobar(s[1]["pedido_sugerido"] == 0, "con stock de sobra, no pide")
    comprobar(s[0]["nivel_objetivo"] >= s[0]["demanda_esperada"], "el nivel objetivo cubre la demanda esperada")

    print("nivel de servicio configurable")
    base = dict(cuerpo, productos=[{"item": "SUPERMARKET_3_511", "stock_actual": 0}])
    bajo = cliente.post("/reposicion/sugerencia", json=dict(base, parametros={"nivel_servicio": 0.80})).json()
    alto = cliente.post("/reposicion/sugerencia", json=dict(base, parametros={"nivel_servicio": 0.98})).json()
    comprobar(alto["sugerencias"][0]["pedido_sugerido"] > bajo["sugerencias"][0]["pedido_sugerido"],
              "más nivel de servicio ⇒ más pedido")

    print("coherencia con el almacén (fact_reposicion)")
    import duckdb
    rep = duckdb.connect().execute(
        f"SELECT * FROM read_parquet('{os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'lakehouse', 'gold', 'fact_reposicion.parquet')}')").df()
    for fecha in ("2016-04-25", "2016-05-16"):        # la segunda es la revisión cuya ventana se sale del horizonte
        muestra = rep[rep["fecha_revision"].astype(str) == fecha].sample(40, random_state=3)
        difs = []
        for _, f in muestra.iterrows():
            j = cliente.post("/reposicion/sugerencia", json={"tienda": f["store_code"], "fecha_revision": fecha,
                             "productos": [{"item": f["item"], "stock_actual": 0}]}).json()["sugerencias"][0]
            difs.append(abs(np.ceil(j["nivel_objetivo"]) - f["nivel_objetivo"]))
        comprobar(max(difs) <= 1, f"la API y el almacén dan el mismo nivel objetivo el {fecha}")

    print("errores")
    comprobar(cliente.post("/reposicion/sugerencia", json=dict(cuerpo, tienda="XXX")).status_code == 404,
              "tienda inexistente devuelve 404")
    comprobar(cliente.post("/reposicion/sugerencia", json=dict(cuerpo, fecha_revision="2020-01-01")).status_code == 400,
              "fecha fuera de horizonte devuelve 400")

print(f"\n{'TODAS LAS PRUEBAS PASAN' if not fallos else str(len(fallos)) + ' FALLOS'}")
sys.exit(1 if fallos else 0)
