# 9. Anexos

Los anexos recogen el material que sostiene el cuerpo de la memoria y al que este remite. Ninguno
es material de relleno: todos están referenciados desde el texto, y el que no lo esté no debe
incluirse.

## Anexo A. Cuadernos de análisis

Cinco cuadernos Jupyter, uno por etapa. Los cuadernos 02, 04 y 05 se generan a partir de un
guion de construcción versionado (`build_notebook_0X.py`) y se ejecutan de principio a fin, de
modo que el cuaderno entregado y el código que lo produce no pueden divergir. El 03 conserva las
salidas de su primera versión, cuyos ficheros intermedios no se pueden regenerar desde el
repositorio; las secciones 15 y 16, añadidas en la revisión, son autocontenidas y se ejecutan con
`actualizar_notebooks.py` a partir de `forecast_segmentacion.py`, `forecast_semanal.py` y
`modelo_final.py`. Las ampliaciones del 01 (apartado 11.1) se añaden con `actualizar_eda.py`.

| Cuaderno | Contenido | Sección |
|---|---|---|
| `01_EDA_DSMarket.ipynb` | Análisis exploratorio, diagnóstico de calidad y eventos vistos por semanas | §7.1 |
| `02_Clustering_DSMarket.ipynb` | Segmentación de productos (método del codo, variables medidas desde la primera venta) y comparación de tiendas | §7.2 |
| `03_Forecasting_DSMarket.ipynb` | Comparación de modelos, validación y reconciliación; revisión con la segmentación actual, métrica semanal, eventos semanales y modelo final de 400 días | §7.3 |
| `04_Abastecimiento_DSMarket.ipynb` | Política de reposición y simulación de costes con las predicciones del modelo final | §7.4 |
| `05_Elasticidad_DSMarket.ipynb` | Estimación de elasticidad y prueba de falsación | §7.5 |

## Anexo B. El almacén analítico

Documentación de la arquitectura descrita en §6.3 y §7.6: las tres capas, el modelo dimensional,
el proceso de construcción y el bucle de realimentación de las predicciones. Incluye el diccionario
de las nueve tablas de la capa de consumo y el procedimiento de reconstrucción íntegra desde los
ficheros de origen.

## Anexo C. El servicio de reposición

Especificación de la interfaz de programación descrita en §7.6.2: operaciones disponibles,
esquema de petición y respuesta, y el conjunto de doce pruebas automáticas con su resultado.

## Anexo D. El panel interactivo

Descripción de la aplicación y de sus cinco pantallas, con capturas. Documenta también la capa de
lenguaje natural y las tres barreras de seguridad descritas en §7.6.3.

## Anexo E. El cuadro de mando

Especificación para su construcción en Power BI: modelo de datos, relaciones, medidas y
disposición de páginas. Incluye el patrón de agregación obligatorio para evitar la multiplicación
de métricas descrita en §7.6.4.

## Anexo F. Manual de ejecución

Procedimiento completo para reproducir el trabajo desde cero: dependencias, orden de ejecución,
tiempos de referencia de cada etapa y resolución de las incidencias conocidas.

## Anexo G. Alternativas evaluadas y descartadas

Los experimentos que se plantearon, se dimensionaron y no se incorporaron al trabajo principal,
con la razón de su descarte. Se incluye porque distingue un trabajo que exploró el espacio de
soluciones de uno que se detuvo en la primera opción que funcionó.
