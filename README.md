# DSMarket — de la venta diaria a la decisión de reposición

Trabajo de Fin de Máster · Máster en Data Science & Inteligencia Artificial · Nuclio Digital
School, Barcelona.

Sistema analítico completo sobre el histórico de ventas de DSMarket, una cadena de distribución
minorista con diez establecimientos en tres ciudades y 3.049 referencias. Va desde el fichero en
bruto hasta la cantidad que debe pedirse de cada producto en cada tienda.

**58.327.370 observaciones diarias · 30.490 series producto-tienda · 2011-2016**

---

## Qué hay aquí

| Carpeta | Contenido |
|---|---|
| `*.ipynb` | Los cinco cuadernos de análisis, uno por etapa, y el experimento complementario `03b` (modelo sin los grupos de producto) |
| `forecast_segmentacion.py`, `forecast_semanal.py`, `modelo_final.py` | Entrenamientos auxiliares del cuaderno 03 (secciones 6, 9 y 11) y el modelo final (sección 12): 400 días de historia y eventos semanales |
| `predicciones_28dias*.csv` | La entrega: predicción media y percentil 90 de los 28 días siguientes, con el modelo final |
| `lakehouse/scripts/` | Construcción del almacén analítico en tres capas |
| `operacion/` | La capa que hace que esto sea un sistema y no un conjunto de cuadernos |
| `app/` | Panel interactivo (Streamlit) |
| `api/` | Servicio de reposición (FastAPI) con sus trece comprobaciones |
| `avanzado/` | Nueve experimentos y sondeos, con sus resultados |
| `memoria/` | La memoria, una sección por fichero, y el `.docx` generado |
| `documentacion/` | Manual de ejecución, teoría, arquitectura, explicación de la app |
| `dashboard/` | Especificación del cuadro de mando en Power BI |

## Lo que no está en el repositorio, y por qué

Tres cosas se ignoran a propósito. Ninguna se pierde: todas se regeneran.

**Los datos de origen** (`data_dsmarket/`, 469 MB) los aporta la escuela y no nos corresponde
redistribuirlos. Colócalos en `data_dsmarket/data_dsmarket/` con sus tres CSV:
`item_sales.csv`, `item_prices.csv` y `daily_calendar_with_events.csv`.

**El almacén** (`lakehouse/bronze|silver|gold`, 163 MB) se reconstruye entero en unos veinte
segundos con un comando.

**La caché de modelos** (`cache_forecast/`, 186 MB) se regenera reentrenando; uno de sus ficheros
pesa 112 MB, por encima del límite de GitHub.

## Puesta en marcha

```bash
conda env create -f environment.yml
conda activate dsmarket
```

O con pip, si prefieres un entorno virtual:

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

En macOS, LightGBM y XGBoost necesitan OpenMP, que el sistema no trae. Por conda viene resuelto;
con pip hace falta `brew install libomp`.

Después, con los datos en su sitio:

```bash
python3 operacion/orquestador.py
```

Un comando ejecuta las diez etapas: construye las tres capas del almacén, comprueba quince
contratos de datos, entrena, somete el candidato a la puerta de promoción, predice a 28 días, calcula los niveles objetivo, vuelve a comprobar
los contratos antes de publicar y ejecuta la monitorización. Se detiene ante el primer fallo
bloqueante y deja constancia de todo.

El manual completo, paso a paso y con tiempos de referencia, está en
`documentacion/instructivo.html`.

## Para ver el proyecto en marcha

```bash
streamlit run app/inicio.py
```

La capa de lenguaje natural es opcional e intercambiable. Funciona **en local y sin coste**:

```bash
ollama serve
ollama pull llama3.1:8b
export DSMARKET_LLM=ollama
```

Con `DSMARKET_LLM=groq`, `gemini`, `openrouter` o `anthropic` se cambia de proveedor sin tocar
código. Sin ninguno configurado, la aplicación funciona igual: las explicaciones se redactan por
reglas.

## Los resultados, en corto

- La demanda no es homogénea: **solo 5 de los 15 productos más vendidos** son comunes a las tres
  ciudades, y el parecido entre tiendas no respeta las fronteras de ciudad.
- **La estrategia de horizonte pesó unas tres veces más que la elección de biblioteca.** Con la
  formulación ingenua los modelos apenas superan a una media móvil.
- Reformular el objetivo como el total del ciclo reduce el error un **15,7%** y elimina un sesgo
  del −7,4%.
- Sumar las predicciones individuales es válido: el enfoque ascendente gana en los cuatro niveles de agregación a Prophet y SARIMA.
- La política de reposición eleva el nivel de servicio del **86,6% al 96,2%** con un 62,5% menos de
  coste; el óptimo lo decide la merma, no el margen.
- La elasticidad precio **no es identificable** con estos datos, y se demuestra con una prueba de
  falsación.

## Lo que más nos importa de este trabajo

Cuatro veces llegamos a una conclusión atractiva y le aplicamos una prueba que podía tumbarla.
Las cuatro veces la prueba la tumbó: el efecto de Black Friday, la métrica con la que elegimos el
modelo, la elasticidad del precio y la afinidad entre productos. Ninguna de las cuatro pruebas
era obligatoria.

## Reproducibilidad

Los cuadernos son la fuente: se editan y se ejecutan directamente como cuadernos Jupyter. El 03 lee los
resultados de los entrenamientos auxiliares guardados en `cache_forecast_sin_clusters/` (reentrenar todo lleva varias horas) que generan
`forecast_segmentacion.py`, `forecast_semanal.py`, `experimentos_t3.py`, `exp_precios_paso.py` y `modelo_final.py`. Las semillas aleatorias están fijadas. El almacén se reconstruye
íntegro desde los ficheros de origen con un solo comando, y quince contratos de datos detienen el
proceso si algo no cuadra.

## Licencia y datos

Código bajo licencia MIT. Los datos de DSMarket pertenecen a Nuclio Digital School y no se
distribuyen con este repositorio.
