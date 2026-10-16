# -*- coding: utf-8 -*-
"""
DSMarket — API de reposición.

Implementa el servicio diseñado en la sección 8 del notebook 04. Tres decisiones de diseño:

1. **La API no predice, lee predicciones.** Los modelos corren en batch y dejan sus salidas
   en el gold del lakehouse; este servicio solo resuelve la aritmética de la política. Así
   responde en milisegundos y el pico de carga de las revisiones semanales no depende de
   que haya un modelo entrenando.
2. **Los parámetros viajan en la petición.** Finanzas puede cambiar el nivel de servicio de
   una categoría, o probarlo en unas tiendas, sin tocar el código ni redesplegar.
3. **Cada sugerencia se explica.** Devolver el segmento, el método y el motivo es lo que
   hace que un encargado de tienda confíe en el número en vez de pedir a ojo.

Arranque:  uvicorn api.main:app --reload    (documentación interactiva en /docs)
"""
from __future__ import annotations
import os
from datetime import date
from typing import Literal

import numpy as np
import pandas as pd
import duckdb
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from scipy.stats import norm

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLD = os.path.join(RAIZ, "lakehouse", "gold")

app = FastAPI(
    title="DSMarket — API de reposición",
    version="1.0",
    description="Convierte las predicciones de demanda en sugerencias de pedido por tienda y producto.",
)

DATOS: dict = {}

@app.on_event("startup")
def cargar_datos() -> None:
    """Carga el gold en memoria al arrancar: son pocos MB y evita ir a disco en cada petición."""
    con = duckdb.connect()
    lee = lambda t: con.execute(f"SELECT * FROM read_parquet('{os.path.join(GOLD, t)}.parquet')").df()
    pred = lee("fact_predicciones")
    pred["fecha"] = pd.to_datetime(pred["fecha"]).dt.date
    DATOS["predicciones"] = pred.set_index(["store_code", "item", "fecha"]).sort_index()
    DATOS["series"] = lee("dim_serie").set_index(["item", "store_code"])
    DATOS["productos"] = lee("dim_producto").set_index("item")
    DATOS["tiendas"] = lee("dim_tienda").set_index("store_code")
    DATOS["horizonte"] = (pred["fecha"].min(), pred["fecha"].max())
    con.close()

# ----------------------------------------------------------------- modelos
class ProductoEntrada(BaseModel):
    item: str = Field(..., examples=["SUPERMARKET_3_069"])
    stock_actual: float = Field(0, ge=0, description="Unidades disponibles ahora en la tienda")
    en_transito: float = Field(0, ge=0, description="Unidades ya pedidas que aún no llegaron")

class Parametros(BaseModel):
    dias_revision: int = Field(7, ge=1, le=28, description="Cada cuántos días se revisa el stock")
    lead_time: int = Field(2, ge=0, le=14, description="Días que tarda el pedido en llegar")
    nivel_servicio: float | None = Field(
        None, gt=0.5, lt=0.999,
        description="Si se omite, se usa el nivel que corresponde al segmento ABC/XYZ de cada producto")

class PeticionReposicion(BaseModel):
    tienda: str = Field(..., examples=["NYC_1"])
    fecha_revision: date = Field(..., examples=["2016-04-25"])
    productos: list[ProductoEntrada]
    parametros: Parametros = Parametros()

class Sugerencia(BaseModel):
    item: str
    segmento: str
    arquetipo: str | None
    demanda_esperada: float
    nivel_objetivo: float
    stock_seguridad: float
    posicion_stock: float
    pedido_sugerido: int
    nivel_servicio_aplicado: float
    metodo: Literal["percentil_empirico", "modelo_cuantilico"]
    confianza: Literal["alta", "media", "baja"]
    motivo: str

class RespuestaReposicion(BaseModel):
    tienda: str
    fecha_revision: date
    cobertura_hasta: date
    sugerencias: list[Sugerencia]
    resumen: dict

# ----------------------------------------------------------------- lógica
# Nivel de servicio objetivo (Tarea 4, secciones 5.1 y 7): lo decide la merma, no el segmento.
# Lo fresco (SUPERMARKET) se queda en el 90%; lo no perecedero, cuyo sobrante se vende la semana
# siguiente, al 95%. Son parámetros de negocio: cuando DSMarket mida la merma real se ajustan aquí.
NIVEL_POR_CATEGORIA = {"SUPERMARKET": .90, "ACCESORIES": .95, "HOME_&_GARDEN": .95}


def nivel_servicio(item: str) -> float:
    return NIVEL_POR_CATEGORIA["SUPERMARKET"] if item.startswith("SUPERMARKET") else .95
CONFIANZA = {"X": "alta", "Y": "media", "Z": "baja"}

def _explicar(celda: str, arquetipo: str | None, metodo: str, servicio: float, cv: float) -> str:
    partes = [f"Segmento {celda}"]
    partes.append("alta facturación" if celda[0] == "A" else
                  "facturación media" if celda[0] == "B" else "baja facturación")
    partes.append({"X": "demanda estable", "Y": "demanda variable", "Z": "demanda errática"}[celda[1]]
                  + f" (CV {cv:.1f})")
    if arquetipo:
        partes.append(f"grupo de producto «{arquetipo}»")
    partes.append("nivel calculado con el histórico, que en series estables es más robusto que el modelo"
                  if metodo == "percentil_empirico"
                  else "nivel calculado con el modelo, que en series erráticas aporta sobre el histórico")
    partes.append(f"objetivo de servicio {servicio:.0%}")
    return "; ".join(partes) + "."

@app.post("/reposicion/sugerencia", response_model=RespuestaReposicion, tags=["reposición"])
def sugerir(peticion: PeticionReposicion) -> RespuestaReposicion:
    """Calcula cuánto pedir de cada producto para llevar el stock al nivel objetivo."""
    if peticion.tienda not in DATOS["tiendas"].index:
        raise HTTPException(404, f"Tienda desconocida: {peticion.tienda}")
    inicio, fin = DATOS["horizonte"]
    if not (inicio <= peticion.fecha_revision <= fin):
        raise HTTPException(400, f"Sin predicciones para esa fecha. Horizonte disponible: {inicio} a {fin}")

    p = peticion.parametros
    cobertura = p.dias_revision + p.lead_time
    fechas = pd.date_range(peticion.fecha_revision, periods=cobertura).date
    fechas = [f for f in fechas if f <= fin]

    sugerencias = []
    for entrada in peticion.productos:
        try:
            bloque = DATOS["predicciones"].loc[(peticion.tienda, entrada.item, fechas), :]
            serie = DATOS["series"].loc[(entrada.item, peticion.tienda)]
        except KeyError:
            raise HTTPException(404, f"Sin datos para {entrada.item} en {peticion.tienda}")

        celda = f"{serie['clase_abc']}{serie['clase_xyz']}"
        servicio = p.nivel_servicio if p.nivel_servicio is not None else nivel_servicio(entrada.item)
        media = float(bloque["prediccion_media"].sum())
        sigma_dia = (bloque["prediccion_p90"] - bloque["prediccion_media"]).clip(lower=0) / norm.ppf(0.90)
        sigma = float(np.sqrt((sigma_dia ** 2).sum()))
        # política híbrida (Tarea 4): en series estables el histórico gana al modelo
        metodo = "percentil_empirico" if serie["clase_xyz"] == "X" else "modelo_cuantilico"
        if metodo == "percentil_empirico":
            nivel = float(serie["media_dia"] * cobertura + norm.ppf(servicio) * serie["desvio_dia"] * np.sqrt(cobertura))
        else:
            nivel = media + norm.ppf(servicio) * sigma
        nivel = max(nivel, 0.0)
        posicion = entrada.stock_actual + entrada.en_transito
        arquetipo = DATOS["productos"].loc[entrada.item, "arquetipo"] if entrada.item in DATOS["productos"].index else None
        sugerencias.append(Sugerencia(
            item=entrada.item, segmento=celda, arquetipo=arquetipo,
            demanda_esperada=round(media, 2), nivel_objetivo=round(nivel, 2),
            stock_seguridad=round(max(nivel - media, 0), 2), posicion_stock=posicion,
            pedido_sugerido=int(np.ceil(max(nivel - posicion, 0))),
            nivel_servicio_aplicado=servicio, metodo=metodo,
            confianza=CONFIANZA[serie["clase_xyz"]],
            motivo=_explicar(celda, arquetipo, metodo, servicio, float(serie["coef_variacion"]))))

    return RespuestaReposicion(
        tienda=peticion.tienda, fecha_revision=peticion.fecha_revision, cobertura_hasta=fechas[-1],
        sugerencias=sugerencias,
        resumen={"productos": len(sugerencias),
                 "unidades_a_pedir": int(sum(s.pedido_sugerido for s in sugerencias)),
                 "productos_sin_pedido": sum(1 for s in sugerencias if s.pedido_sugerido == 0)})

@app.get("/prediccion/{tienda}/{item}", tags=["predicción"])
def prediccion(tienda: str, item: str,
               dias: int = Query(28, ge=1, le=28, description="Días de horizonte a devolver")):
    """Serie de predicción diaria (valor central y percentil 90) de un producto en una tienda."""
    try:
        bloque = DATOS["predicciones"].loc[(tienda, item)].head(dias)
    except KeyError:
        raise HTTPException(404, f"Sin predicciones para {item} en {tienda}")
    return {"tienda": tienda, "item": item,
            "predicciones": [{"fecha": str(f), "media": round(r.prediccion_media, 3),
                              "p90": round(r.prediccion_p90, 3)} for f, r in bloque.iterrows()]}

@app.get("/tiendas", tags=["catálogo"])
def tiendas():
    """Tiendas disponibles, con la tienda más parecida a cada una (Tarea 2, sección 5.3)."""
    return DATOS["tiendas"].reset_index().to_dict("records")

@app.get("/segmentos", tags=["catálogo"])
def segmentos():
    """Distribución del catálogo por celda ABC/XYZ y método de reposición aplicado a cada una."""
    s = DATOS["series"].reset_index()
    s["celda"] = s["clase_abc"] + s["clase_xyz"]
    resumen = (s.groupby("celda")
                 .agg(series=("item", "count"), facturacion_90d=("facturacion_90d", "sum"))
                 .reset_index())
    resumen["pct_facturacion"] = (resumen["facturacion_90d"] / resumen["facturacion_90d"].sum() * 100).round(1)
    resumen["metodo"] = resumen["celda"].str[1].map(
        {"X": "percentil_empirico", "Y": "modelo_cuantilico", "Z": "modelo_cuantilico"})
    return resumen.drop(columns="facturacion_90d").to_dict("records")

@app.get("/salud", tags=["operación"])
def salud():
    """Comprobación de vida y de qué datos tiene cargados el servicio."""
    inicio, fin = DATOS["horizonte"]
    return {"estado": "ok", "series_con_prediccion": int(len(DATOS["series"])),
            "horizonte_desde": str(inicio), "horizonte_hasta": str(fin)}
