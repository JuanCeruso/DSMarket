# 9. Anexos

Los anexos recogen el material que sostiene el cuerpo de la memoria y al que este remite. Ninguno
es material de relleno: todos están referenciados desde el texto, y el que no lo esté no debe
incluirse.

## Anexo A. Cuadernos de análisis

Cinco cuadernos Jupyter, uno por etapa, ejecutables de principio a fin. Cada uno se genera a
partir de un guion de construcción versionado, de modo que el cuaderno entregado y el código que
lo produce no pueden divergir.

| Cuaderno | Contenido | Sección |
|---|---|---|
| `01_EDA_DSMarket.ipynb` | Análisis exploratorio y diagnóstico de calidad | §7.1 |
| `02_Clustering_DSMarket.ipynb` | Segmentación de productos y tiendas, clasificación ABC/XYZ | §7.2 |
| `03_Forecasting_DSMarket.ipynb` | Comparación de modelos, validación y reconciliación | §7.3 |
| `04_Abastecimiento_DSMarket.ipynb` | Política de reposición y simulación de costes | §7.4 |
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
