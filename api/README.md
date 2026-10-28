# DSMarket — API de reposición

Implementación del servicio diseñado en la sección 8 del notebook `04_Abastecimiento_DSMarket.ipynb`.
El enunciado pedía solo el diseño; esto es el diseño funcionando.

## Arrancar

```bash
pip install fastapi "uvicorn[standard]" duckdb pandas scipy
cd PROYECTO
uvicorn api.main:app --reload
```

Documentación interactiva navegable en **http://127.0.0.1:8000/docs** — se puede probar cada
endpoint desde el navegador sin escribir una línea de código. Es la forma más rápida de
enseñarlo en la defensa.

## Endpoints

| Método | Ruta | Para qué |
|---|---|---|
| `POST` | `/reposicion/sugerencia` | El principal: cuánto pedir de cada producto |
| `GET` | `/prediccion/{tienda}/{item}` | Serie de predicción diaria (media y p90) |
| `GET` | `/tiendas` | Catálogo de tiendas con su tienda más parecida (Tarea 2) |
| `GET` | `/segmentos` | Distribución ABC/XYZ y método de reposición de cada celda |
| `GET` | `/salud` | Comprobación de vida y horizonte de datos cargado |

### Ejemplo

```bash
curl -X POST http://127.0.0.1:8000/reposicion/sugerencia \
  -H "Content-Type: application/json" -d '{
    "tienda": "NYC_1",
    "fecha_revision": "2016-04-25",
    "productos": [{"item": "SUPERMARKET_3_511", "stock_actual": 180, "en_transito": 30}],
    "parametros": {"dias_revision": 7, "lead_time": 2}
  }'
```

```json
{
  "item": "SUPERMARKET_3_511",
  "segmento": "AX",
  "arquetipo": "Pico de diciembre",
  "demanda_esperada": 189.47,
  "nivel_objetivo": 239.27,
  "stock_seguridad": 49.8,
  "posicion_stock": 210.0,
  "pedido_sugerido": 30,
  "nivel_servicio_aplicado": 0.9,
  "metodo": "percentil_empirico",
  "confianza": "alta",
  "motivo": "Segmento AX; alta facturación; demanda estable (CV 0.4); grupo de producto «Pico de diciembre»; nivel calculado con el histórico, que en series estables es más robusto que el modelo; objetivo de servicio 90%."
}
```

## Las tres decisiones de diseño

**1. La API no predice, lee predicciones.** Los modelos corren en batch y dejan sus salidas en
`lakehouse/gold/fact_predicciones.parquet`. El servicio carga esa tabla al arrancar (5,4 MB) y
resuelve cada petición con aritmética sobre memoria. Consecuencia: responde en milisegundos, y
el pico de las revisiones semanales no compite con ningún entrenamiento.

**2. Los parámetros viajan en la petición.** `dias_revision`, `lead_time` y `nivel_servicio` son
del cliente, no del código. Finanzas puede subir el nivel de servicio de una categoría, o
probarlo en dos tiendas antes de extenderlo, sin redesplegar nada. Si no se envía
`nivel_servicio`, cada producto usa el de su categoría: 90% en SUPERMARKET y 95% en ACCESORIES y
HOME_&_GARDEN (Tarea 4, sección 7: lo decide la merma).

**3. Cada sugerencia se explica.** La respuesta incluye `segmento`, `metodo`, `confianza` y un
`motivo` en lenguaje natural. No es decoración: en la sección 8 del notebook 04 identificamos
que el riesgo real del proyecto es que el encargado de tienda ignore el número y pida a ojo.
Un número que se explica se discute; uno que no, se descarta.

## La política que aplica

Es la política híbrida validada en la Tarea 4: **percentil empírico** para las series de demanda
estable (clase X) y **modelo cuantílico** para las variables y erráticas (Y, Z). En la simulación
esa combinación dominó a las dos alternativas puras — mejor nivel de servicio *y* menor coste.

El nivel objetivo cubre el ciclo de revisión más el plazo de entrega:

```
nivel_objetivo = demanda_esperada(R+L días) + z(nivel_servicio) · σ(R+L días)
pedido         = max(nivel_objetivo − stock_actual − en_transito, 0)
```

## Pruebas

```bash
python3 api/test_api.py     # arranca el servicio, ejerce los endpoints y valida las respuestas
```
