---


# 9. Anexos

Los anexos recogen el material que sostiene el cuerpo de la memoria y al que este remite. Todos
están referenciados desde el texto principal; el código fuente completo y los cuadernos se
entregan junto con este documento.

## Anexo A. Cuadernos de análisis y entrenamientos auxiliares

El trabajo analítico se articula en cinco cuadernos Jupyter, uno por etapa, que constituyen la
fuente de todas las cifras de la memoria. Las semillas aleatorias están fijadas y cada cuaderno se
ejecuta de principio a fin sin intervención manual.

| Cuaderno | Contenido | Sección |
|---|---|---|
| `01_EDA_DSMarket.ipynb` | Análisis exploratorio, diagnóstico de calidad y eventos vistos por semanas | §7.1 |
| `02_Clustering_DSMarket.ipynb` | Segmentación de productos (método del codo, variables medidas desde la primera venta) y comparación de tiendas | §7.2 |
| `03_Forecasting_DSMarket.ipynb` | Comparación de modelos, validación y reconciliación; revisión sin la variable de grupo de producto, métrica semanal, eventos semanales y modelo final de 400 días | §7.3 |
| `04_Abastecimiento_DSMarket.ipynb` | Política de reposición y simulación de costes con las predicciones del modelo final | §7.4 |
| `05_Elasticidad_DSMarket.ipynb` | Estimación de elasticidad y prueba de falsación | §7.5 |

El cuaderno 03 se apoya en cinco módulos de entrenamiento (`forecast_segmentacion.py`,
`forecast_semanal.py`, `experimentos_t3.py`, `exp_precios_paso.py` y `modelo_final.py`) cuyos
resultados se guardan en un directorio de caché no versionado, ya que reentrenar el conjunto
completo requiere varias horas. El cuaderno complementario `03b_Forecasting_sin_clusters_DSMarket.ipynb`
contiene la comparación del modelo con y sin la variable de grupo de producto citada en §7.8.

Los ficheros de entrega de la predicción son `predicciones_28dias.csv` (media) y
`predicciones_28dias_p90.csv` (percentil 90), ambos de 30.490 series por 28 días, del 25 de abril
al 22 de mayo de 2016.

## Anexo B. El almacén analítico

**Arquitectura.** El almacén son ficheros Parquet organizados en tres capas; el motor de
consulta (DuckDB) se inicia, registra las vistas, consulta y se detiene sin conservar estado
propio. Esta separación entre almacenamiento y cómputo es la que utilizan las plataformas
gestionadas en la nube, de modo que la migración consiste en sustituir el motor y la ruta de los
ficheros, no los datos ni las transformaciones. Los 490,9 MB de CSV de origen ocupan 22,1 MB en la
capa bronce y el grano completo de ventas (58,3 millones de filas) 83 MB.

| Capa | Contenido | Regla |
|---|---|---|
| Bronce | Copia fiel de las tres fuentes, sin transformar | No se modifica: es la trazabilidad |
| Plata | Datos limpios, tipados y en formato largo | Contiene las reglas de negocio derivadas del análisis exploratorio |
| Oro | Modelo dimensional en estrella y tablas agregadas | Es lo que consumen el cuadro de mando, la interfaz de programación y los modelos |

**Reglas de negocio codificadas en la capa plata.**

1. *Alineación de precios.* El fichero de precios comienza cinco semanas antes que el de ventas;
   el desfase se calcula anclando el rango de semanas al final. El control de calidad
   correspondiente exige que no haya ventas positivas sin precio.
2. *Eventos derivados por regla de fecha.* Navidad (25 de diciembre) y Labor Day (primer lunes de
   septiembre) no figuran en el calendario original y se incorporan.
3. *Días de cierre.* Solo Navidad se marca como día de cierre, porque la tienda no abre y ningún
   modelo debe predecir ventas ese día. Acción de Gracias no cierra (vende un 28 % menos que un
   jueves normal).

**Diccionario de la capa oro.**

| Tabla | Grano | Filas |
|---|---|---|
| `dim_calendario` | día (incluye los 28 días de horizonte) | 1.941 |
| `dim_producto` | producto, con su grupo de comportamiento | 3.049 |
| `dim_tienda` | tienda, con la tienda más parecida | 10 |
| `dim_serie` | producto × tienda, con clase ABC/XYZ | 30.490 |
| `fact_ventas` | producto × tienda × día, valorizado | 58.327.370 |
| `fact_predicciones` | producto × tienda × día futuro (media y percentil 90) | 853.720 |
| `fact_reposicion` | producto × tienda × revisión (nivel objetivo y stock de seguridad) | 121.960 |
| `mart_ventas_dia` | día × tienda × departamento | 133.910 |
| `mart_producto_tienda` | producto × tienda, agregados | 30.490 |

Las tablas `fact_predicciones` y `fact_reposicion` constituyen el bucle de realimentación: las
salidas de los modelos regresan al almacén, de modo que todos los consumidores leen de la misma
fuente.

**Controles de calidad superados.** Ventas con unidades positivas y sin precio: 0. Claves
duplicadas en `dim_serie`, `dim_producto` y `fact_predicciones`: 0. Series de `fact_ventas` sin
fila en las dimensiones: 0. Predicciones con percentil 90 inferior a la media: 0 tras la
corrección descrita en §7.6.4. Fechas de predicción ausentes del calendario: 0. Coincidencia de
unidades entre `mart_ventas_dia` y `fact_ventas`.

**Dos precisiones.** La clasificación ABC/XYZ de `dim_serie` se calcula con los últimos 90 días
disponibles (hasta el 24 de abril de 2016), mientras que el cuaderno 04 clasifica con los 90 días
anteriores a la ventana simulada (hasta el 27 de marzo); por ello los recuentos difieren
ligeramente (5.634 series AX frente a 5.494). Además, el 20 % de los días de `fact_ventas` carece
de precio por ser anterior al inicio de venta del producto en la tienda; ninguno de ellos registra
ventas.

**Reconstrucción íntegra.** El almacén completo se regenera desde los ficheros de origen en unos
veinte segundos mediante `scripts/pipeline.py all`, seguido de las cargas de predicciones,
grupos, precios y similitud, y de la exportación a CSV para el cuadro de mando, que debe ejecutarse
siempre en último lugar.

## Anexo C. El servicio de reposición

El servicio, desarrollado con FastAPI, implementa el diseño pedido en el enunciado. No predice:
lee de `fact_predicciones` al arrancar (5,4 MB) y resuelve cada petición con aritmética sobre
memoria, de modo que responde en milisegundos y los entrenamientos no compiten con las consultas.

| Método | Ruta | Función |
|---|---|---|
| `POST` | `/reposicion/sugerencia` | Cantidad que debe pedirse de cada producto |
| `GET` | `/prediccion/{tienda}/{item}` | Serie de predicción diaria (media y percentil 90) |
| `GET` | `/tiendas` | Catálogo de tiendas con su tienda más parecida |
| `GET` | `/segmentos` | Distribución ABC/XYZ y método de reposición de cada celda |
| `GET` | `/salud` | Comprobación de vida y horizonte de datos cargado |

**Petición.** Una tienda, una fecha de revisión, una lista de productos con su stock actual y
mercancía en tránsito, y parámetros opcionales (`dias_revision`, `lead_time`, `nivel_servicio`).
Los parámetros viajan en la petición y no en el código, de modo que el nivel de servicio puede
modificarse por categoría sin redesplegar. Si se omite, cada producto aplica el de su categoría
(90 % en SUPERMARKET; 95 % en ACCESORIES y HOME_&_GARDEN).

**Respuesta.** Por producto: segmento ABC/XYZ, grupo de comportamiento, demanda esperada, nivel
objetivo, stock de seguridad, posición de stock, pedido sugerido, nivel de servicio aplicado,
método, grado de confianza y un motivo en lenguaje natural. Este último campo responde a una
decisión de diseño: un número que se explica puede discutirse; uno que no se explica tiende a
descartarse.

**Política aplicada.** Es la política híbrida de §7.4: percentil empírico para las series de
demanda estable (clase X) y modelo cuantílico para las variables y erráticas (Y y Z).

$$
S = \hat{\mu}_{R+L} + z_{\tau}\,\hat{\sigma}_{R+L}, \qquad
\text{pedido} = \max\left(S - \text{stock} - \text{tránsito},\, 0\right)
$$

**Verificación.** El fichero `api/test_api.py` arranca el servicio en proceso y ejerce los
endpoints con trece comprobaciones.

## Anexo D. El panel interactivo

La aplicación, desarrollada con Streamlit, lee el almacén directamente y aplica la misma política
que el servicio. Dispone de seis pestañas:

| Pestaña | Función |
|---|---|
| Hoy en la tienda | Lista de trabajo del día: referencias que deben pedirse, ordenadas por el coste de no pedirlas, con columna de pedido final editable |
| Reposición | Selección de tienda y producto, histórico y previsión con banda del percentil 90, y cálculo de la cantidad a pedir con su justificación |
| Explorador del catálogo | Matriz ABC/XYZ y mayores pedidos sugeridos de la tienda seleccionada |
| Curva de servicio | Coste de cada punto de nivel de servicio, con control de la merma para observar el desplazamiento del óptimo |
| Preguntar | Consultas en lenguaje natural traducidas a SQL sobre el almacén |
| Cómo se integra | Petición y respuesta JSON equivalentes del servicio y diagrama del flujo completo |

**Capa de lenguaje natural.** Es opcional: el panel funciona por completo sin ella. El proveedor
del modelo de lenguaje se selecciona mediante la variable de entorno `DSMARKET_LLM` (Anthropic,
Groq, Gemini u OpenRouter). Rige la regla de que el modelo de lenguaje nunca calcula, materializada
en tres barreras descritas en §7.6.3: el contexto del redactor contiene cifras ya resueltas, el
componente de consulta genera SQL y no respuestas, y el SQL atraviesa un validador que admite
únicamente sentencias de lectura (`SELECT` o `WITH`) sobre las nueve vistas conocidas, rechaza
sentencias múltiples y añade un límite de filas.

## Anexo E. El cuadro de mando

El cuadro de mando se construye en Power BI sobre el proyecto en formato de texto (PBIP/TMDL), lo
que permite su control de versiones. Importa los CSV exportados desde la capa oro mediante el
parámetro `RutaGold`.

**Modelo de datos.** Esquema en estrella con las dimensiones de calendario, producto, tienda,
serie, arquetipo y categoría; las tablas de hechos `fact_predicciones`, `fact_reposicion` y
`fact_ventas_reciente` (últimos meses de ventas diarias, que permite filtrar por producto la
página de previsión sin cargar los 58 millones de filas); y las tablas agregadas de ventas,
precios, perfil de producto y distancia entre tiendas. Las medidas se concentran en una tabla
propia.

**Páginas.**

1. Resumen ejecutivo.
2. Comparativa de ciudades y tiendas.
3. Cómo se compra.
4. Precios.
5. Grupos de producto.
6. Explorador de productos.
7. Parecido de tiendas.
8. Previsión de ventas, con banda de incertidumbre controlada por un parámetro de nivel de
   confianza (50 a 99 %).
9. Reposición.
10. Colchón de seguridad.
11. Campana de estimación.

**Patrón de agregación obligatorio.** Las tablas de hechos de grano diario (`fact_ventas`) y
semanal (`fact_reposicion`) no pueden relacionarse directamente: la unión multiplica por siete las
métricas del lado semanal (la trampa del abanico descrita en §7.6.4). Cada hecho debe agregarse
por separado y combinarse después por las claves comunes de tienda y producto.

## Anexo F. Manual de ejecución

**Entorno.** Python 3.12 con las dependencias de `environment.yml` (conda-forge) o
`requirements.txt`. En macOS, LightGBM y XGBoost requieren OpenMP, que el entorno de conda
incluye.

**Ejecución completa.** Un único comando ejecuta las diez etapas del flujo de operación:

```bash
python3 operacion/orquestador.py
```

Las etapas son bronce, plata, oro, contratos, entrenamiento, puerta de promoción, predicción,
reposición, segunda pasada de contratos y monitorización. El flujo se detiene ante el primer fallo
bloqueante y puede reanudarse desde la etapa que falló. El estado de cada ejecución, el registro de
modelos, la procedencia y las alertas se persisten en `lakehouse/gold/operacion/`.

**Ejecución por componentes.**

```bash
python3 lakehouse/scripts/pipeline.py all        # capas bronce, plata y oro
python3 -m pytest pruebas                        # 86 pruebas, sin datos de origen
uvicorn api.main:app                             # servicio de reposición
streamlit run app/inicio.py                      # panel interactivo
```

**Cuadernos.** Se ejecutan en orden numérico. El cuaderno 03 lee los resultados de los
entrenamientos auxiliares de la caché; si esta no existe, deben regenerarse con los módulos
descritos en el Anexo A.

**Integración continua.** El flujo definido en `.github/workflows/ci.yml` ejecuta la suite de pruebas en
cada cambio, con un entorno mínimo que no incluye las bibliotecas de modelado.

## Anexo G. Alternativas evaluadas y descartadas

Se planteó un conjunto de experimentos adicionales cuyo propósito era acotar el espacio de
soluciones. Se resumen a continuación con su resultado; los guiones están en `avanzado/` y los
resultados en `avanzado/resultados/`.

| Experimento | Resultado | Destino |
|---|---|---|
| Selección del modelo por coste en lugar de error | El criterio por coste sitúa el nivel de servicio uniforme del 90 % como 2,45 veces más caro que la mejor alternativa | Incorporado en §7.4 |
| Objetivo agregado (total del ciclo en lugar de suma diaria) | Reduce el MAE un 15,7 % (de 4,73 a 3,99) y elimina un sesgo del −7,4 % | Incorporado en §7.3 |
| Acotación de la demanda censurada | Entre 4,79 % y 14,83 % de unidades no observadas; la conclusión de reposición se refuerza | Incorporado en §6.2.4 y §7.4.7 |
| Búsqueda de hiperparámetros (Optuna) | WRMSSE de validación 0,9788 con la configuración original y 0,9790 con la afinada: el modelo está en una zona plana | Descartado |
| Predicción conforme | Cobertura del 89,9 % sin ajustar y del 90,5 % con garantía formal; la clase Z queda en el 91,8 % | Referido en §7.3 |
| Afinidad de demanda entre productos | Las parejas de una misma tienda no superan el ruido medido entre tiendas distintas: sin señal | §7.2.6 |
| Arranque en frío | Copiar la referencia de la tienda más parecida alcanza un MAE de 0,918 unidades/día, un 34,6 % mejor que la media de la categoría (1,404) y mejor que un modelo por atributos (1,028) | §7.8 |
| Surtido: candidatas a descatalogar | Ranking de series de la celda CZ con dos frenos (referencia única del departamento y rotación superior en la tienda) | §7.8 |
| Redes neuronales (NHITS, TFT) | No ejecutado: la literatura de la competición M5 señala la superioridad de los conjuntos de árboles | Descartado |

Un resultado negativo bien documentado —la elasticidad no identificable, la ausencia de afinidad,
la meseta de hiperparámetros— forma parte del valor del trabajo, porque delimita lo que los datos
permiten afirmar.
