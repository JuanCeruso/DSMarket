# 4. Justificación y contextualización

## 4.1. El contexto de DSMarket

DSMarket opera diez establecimientos en tres ciudades del noreste de Estados Unidos con un
catálogo de 3.049 referencias. Su situación es la habitual en cadenas de distribución de tamaño
medio: dispone de un registro operativo completo —más de cinco años de ventas diarias por
producto y tienda— y carece de un proceso que convierta ese registro en decisiones. La
reposición se decide con criterio de tienda, las campañas se diseñan sobre el catálogo entero y
los precios se fijan sin una medida del efecto que producen.

El plan estratégico de la compañía contempla migrar sus fuentes y procesos de datos a una
plataforma en la nube. Ese plan es el marco en el que se inscribe este trabajo, y explica que la
memoria dedique un capítulo completo a la infraestructura analítica y no solo a los modelos: el
encargo no es producir un informe sino dejar instalada una capacidad.

El tamaño de la compañía condiciona el planteamiento de forma menos evidente de lo que parece.
Diez establecimientos son demasiados para que la reposición se gobierne con el criterio
individual de cada encargado sin que aparezcan divergencias, y demasiado pocos para justificar la
infraestructura distribuida y el equipo especializado que emplean las grandes cadenas. El
proyecto se sitúa deliberadamente en esa franja intermedia: métodos contrastados de la literatura
sobre una infraestructura que una organización de este tamaño puede operar y mantener.

El horizonte de decisión también viene dado por el negocio y no por el análisis. Las cuatro
semanas que el encargo fija como horizonte de previsión no son una elección metodológica: son el
ciclo de compra de la compañía, y determinan tanto la estructura de los modelos como el diseño de
la política de reposición.

## 4.2. Por qué la decisión de reposición es el problema

La distribución minorista de alimentación opera con márgenes brutos estrechos y volúmenes muy
altos, una combinación que convierte las decisiones repetidas de bajo importe unitario en la
principal palanca de resultado. La reposición es la más repetida de todas: se toma para cada
referencia, en cada tienda, cada semana.

Equivocarse tiene dos costes de naturaleza distinta y magnitud muy desigual. El **exceso** de
inventario inmoviliza capital, ocupa espacio y, en producto perecedero, se descarta. La
**rotura** de stock, en cambio, no solo pierde la venta del momento: el estudio de referencia
sobre disponibilidad en lineal de Gruen, Corsten y Bharadwaj (2002), realizado sobre ocho
categorías en más de veinte países, sitúa la tasa media mundial de rotura en el **8,3%** y
documenta que, ante un producto ausente, solo el 15% de los clientes aplaza la compra: el 31%
la realiza en otro establecimiento, el 45% sustituye por otro producto o marca y el 9% renuncia.
Es decir, la mayor parte del efecto de una rotura no se observa en la serie del producto
afectado, y una fracción sustancial se traduce en tráfico que se va a la competencia.

Esta asimetría es la razón por la que el trabajo abandona en §7.4 las métricas de error y pasa a
expresar los resultados en unidades monetarias. También explica por qué el diagnóstico económico
de la política de partida —catorce dólares de margen perdido por cada dólar de inventario
inmovilizado— orienta toda la optimización posterior en una única dirección.

## 4.3. Por qué el problema no es trivial

La previsión de demanda en distribución minorista presenta una combinación de dificultades que
la distingue de otros problemas de series temporales.

**La escala y la granularidad.** El objeto de decisión no es la serie agregada de la cadena sino
cada una de las 30.490 combinaciones de producto y tienda. A ese nivel de desagregación la señal
es débil y el ruido domina.

**La intermitencia.** Una proporción muy alta de las observaciones diarias es cero. La demanda
intermitente invalida los supuestos distribucionales habituales y las métricas de error
relativo, y constituye un área de estudio propia desde el trabajo seminal de Croston (1972) y su
corrección posterior por Syntetos y Boylan (2001).

**La estructura jerárquica.** Las series se agregan de forma natural por tienda, ciudad,
departamento y categoría, y la organización necesita previsiones coherentes en todos esos
niveles: la suma de las previsiones de las tiendas de una ciudad debe coincidir con la previsión
de esa ciudad, o los informes de dirección y de operaciones se contradicen.

**La asimetría del coste del error.** Equivocarse por exceso y por defecto no cuesta lo mismo, y
por tanto la métrica con la que se evalúa el modelo y la que describe el impacto en la compañía
no coinciden. Esta observación, que en la literatura de previsión se aborda desde la teoría de
las funciones de pérdida y en la de inventarios desde el problema del vendedor de periódicos,
resultó ser central en este trabajo.

## 4.4. Estado del arte

### 4.4.1. Previsión de demanda a gran escala

La referencia obligada en este dominio es la competición M5 (Makridakis, Spiliotis y
Assimakopoulos, 2022), construida precisamente sobre datos de ventas diarias de una cadena
minorista con estructura jerárquica y demanda intermitente, es decir, sobre un problema
estructuralmente idéntico al de este trabajo. Sus conclusiones orientan varias decisiones de
diseño adoptadas aquí.

La primera es la superioridad de los **ensambles de árboles de decisión con potenciación del
gradiente** sobre las arquitecturas neuronales y sobre los métodos estadísticos clásicos en
problemas de esta naturaleza. La segunda es la ventaja de los **modelos globales** —un único
modelo entrenado sobre todas las series— frente a los modelos locales ajustados serie a serie,
distinción que Januschowski et al. (2020) formalizan como criterio de clasificación de métodos
de previsión. La tercera, procedente de la competición de incertidumbre paralela (Makridakis et
al., 2022b), es que la evaluación probabilística requiere reglas de puntuación propias y no
puede derivarse de la evaluación puntual.

Las implementaciones empleadas en este trabajo son LightGBM (Ke et al., 2017) y XGBoost (Chen y
Guestrin, 2016) para los modelos globales, y Prophet (Taylor y Letham, 2018) junto con los
modelos SARIMA descritos en Hyndman y Athanasopoulos (2021) como contraste de familia. La
revisión de Petropoulos et al. (2022) proporciona el marco general de referencia sobre el estado
de la disciplina.

### 4.4.2. Previsión probabilística

La decisión de reposición no necesita la demanda esperada sino un cuantil de su distribución, lo
que sitúa el problema en el terreno de la previsión probabilística. La regresión cuantílica de
Koenker y Bassett (1978) proporciona el instrumento directo, mediante la minimización de la
función de pérdida asimétrica conocida como pérdida pinball. Gneiting y Raftery (2007)
establecen el marco de las reglas de puntuación estrictamente propias que justifica su uso como
criterio de evaluación. Romano, Patterson y Candès (2019) extienden el enfoque con la predicción
conforme cuantílica, que convierte la cobertura empírica en una garantía de cobertura en muestra
finita sin supuestos distribucionales.

### 4.4.3. Reconciliación jerárquica

El problema de obtener previsiones coherentes en una jerarquía de agregación tiene tres
soluciones clásicas —ascendente, descendente y por niveles— superadas por el enfoque de
combinación óptima de Hyndman, Ahmed, Athanasopoulos y Shang (2011) y su refinamiento posterior,
el método MinT de Wickramasuriya, Athanasopoulos y Hyndman (2019), que obtiene la reconciliación
minimizando la traza de la matriz de covarianzas del error de reconciliación. Este último es el
método empleado en §7.3.8, y su propiedad más valiosa para la organización no es la mejora del
error sino la garantía de coherencia entre niveles.

### 4.4.4. Teoría de inventarios

El problema de determinar la cantidad óptima ante demanda incierta se remonta a la formulación
del vendedor de periódicos de Arrow, Harris y Marschak (1951), cuya solución —el cuantil de la
distribución de demanda determinado por el ratio crítico entre el coste de escasez y el coste
total— es el fundamento de la política desarrollada en §7.4. Los tratados de Silver, Pyke y
Thomas (2016) y Zipkin (2000) proporcionan las políticas de revisión periódica, el
dimensionamiento del stock de seguridad y la clasificación ABC/XYZ empleadas en este trabajo.

La conexión entre este marco y el de la previsión probabilística —la equivalencia entre el coste
esperado del vendedor de periódicos y la pérdida pinball evaluada en el ratio crítico— es la que
articula los capítulos §7.3 y §7.4 de esta memoria y la que sostiene su principal aportación
metodológica.

### 4.4.5. Segmentación y datos composicionales

La segmentación de productos y tiendas emplea métodos clásicos de agrupamiento cuya validación
se apoya en el coeficiente de silueta (Rousseeuw, 1987), el índice de Davies y Bouldin (1979) y
el de Caliński y Harabasz (1974), junto con el índice de Rand ajustado de Hubert y Arabie (1985)
para medir la concordancia entre particiones. La limitación metodológica reconocida en §7.2.1
—el tratamiento de perfiles normalizados como si vivieran en un espacio euclídeo— corresponde al
problema de los datos composicionales formulado por Aitchison (1982).

### 4.4.6. Identificación del efecto del precio

La estimación de la elasticidad precio a partir de datos observacionales de escáner tiene una
literatura extensa y un problema central reconocido: la endogeneidad del precio, que los
comercios fijan en función de la demanda esperada. Berry, Levinsohn y Pakes (1995) establecen el
tratamiento canónico mediante variables instrumentales en modelos de demanda diferenciada;
Villas-Boas y Winer (1999) documentan la magnitud del sesgo cuando el problema se ignora; y
Bijmolt, van Heerde y Pieters (2005) sintetizan las generalizaciones empíricas disponibles sobre
la magnitud de las elasticidades en bienes de consumo.

La estrategia de identificación empleada en §7.5 —modelo de panel con efectos fijos de serie y
de tiempo, estimado mediante proyecciones alternadas siguiendo a Guimarães y Portugal (2010) y
Correia (2017), que son la implementación práctica del teorema de Frisch y Waugh (1933) y Lovell
(1963)— y la prueba de falsación que la desmiente siguen el enfoque de diseño de investigación
descrito en Angrist y Pischke (2009).

### 4.4.7. Arquitectura de datos analíticos

El modelo dimensional en estrella empleado en la capa de consumo procede de Kimball y Ross
(2013). La organización en capas sucesivas de refinamiento —bronce, plata y oro— corresponde a
la arquitectura *lakehouse* descrita por Armbrust et al. (2021), que combina el almacenamiento
en formatos abiertos propio del lago de datos con las garantías transaccionales y el modelo
dimensional del almacén clásico. El motor empleado, DuckDB (Raasveldt y Mühleisen, 2019),
representa la categoría de bases de datos analíticas embebidas, adecuada para volúmenes que
resultan grandes para una biblioteca en memoria y pequeños para una infraestructura distribuida.

## 4.5. Aportación de este trabajo

El trabajo no propone un método nuevo. Su aportación es de otro tipo, y se concreta en tres
puntos.

**La cadena completa.** La mayoría de los trabajos de este ámbito se detienen en la métrica de
error. Este llega hasta la unidad pedida y expresa el resultado en dinero, lo que permite
observar que la ordenación de los modelos por error y por coste no coinciden.

**La formulación explícita del criterio de selección.** La equivalencia entre el coste del
vendedor de periódicos y la pérdida pinball en el ratio crítico está presente en ambas
literaturas por separado; su uso como criterio de selección de modelo, sustituyendo a una
métrica simétrica, es lo que este trabajo propone y documenta.

**El uso sistemático de pruebas de falsación.** Cada conclusión relevante se acompaña de la
prueba que la habría desmentido. En tres ocasiones la prueba desmintió efectivamente una
conclusión propia, y esos tres casos se documentan como resultado y no como incidencia.
