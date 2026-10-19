# 6. Metodología

Esta sección reúne una sola vez el aparato común a todos los capítulos de resultados: de dónde
salen los datos, qué se hizo con ellos antes de analizarlos, sobre qué infraestructura se
apoyó el trabajo, cómo se validó cada modelo y con qué métricas se juzgó. Los capítulos de la
sección 7 remiten aquí en lugar de repetir el método.

## 6.1. Origen y descripción de los datos

El material de partida son tres ficheros planos que suman 490,9 MB.

**`item_sales.csv`** contiene las unidades vendidas en formato ancho: una fila por combinación de
producto y tienda, y 1.913 columnas `d_1` … `d_1913`, una por día. Incorpora además los
atributos de la referencia (identificador, departamento, categoría) y de la tienda
(identificador, nombre, ciudad). Las 30.490 filas resultan del producto de 3.049 referencias
por 10 tiendas: el panel está completo, todas las referencias existen en todas las tiendas.

**`item_prices.csv`** recoge el precio de venta con granularidad semanal por producto y tienda,
identificando la semana mediante un código `wm_yr_wk`. Es, con 370 MB, el fichero más grande
del conjunto pese a ser el de menor cardinalidad conceptual.

**`daily_calendar_with_events.csv`** hace de tabla puente entre ambos: asocia cada día `d_n` con
su fecha natural y su código de semana, y añade el nombre y el tipo del evento cuando lo hay.

El período cubierto va del 29 de enero de 2011 al 24 de abril de 2016: 1.913 días, cinco años y
casi tres meses. Desplegado a formato largo, el histórico de ventas asciende a **58.327.370
observaciones diarias** de producto, tienda y día.

### 6.1.1. La unidad de análisis

El trabajo emplea de forma sistemática la **serie producto-tienda** como unidad elemental: la
misma referencia en dos establecimientos distintos es, a todos los efectos, dos series
independientes. Hay 30.490. Esta elección no es neutral —implica renunciar a modelar la
sustitución entre tiendas cercanas— pero se corresponde con la unidad sobre la que se toma la
decisión de reposición, que es el destino final del análisis.

## 6.2. Calidad de los datos y decisiones de tratamiento

### 6.2.1. El desfase entre precios y ventas

La comprobación de integridad más relevante del trabajo surgió al cruzar los dos ficheros
principales. El histórico de precios **comienza cinco semanas antes que el de ventas**. Una
lectura ingenua del cruce interpretaría esas semanas como períodos con precio y sin demanda, es
decir, como ceros de venta, e introduciría un sesgo a la baja en todas las medias y en todos los
modelos entrenados sobre ellas.

La hipótesis se contrastó de forma directa: se contaron las unidades vendidas en las
combinaciones producto-tienda-semana **sin** precio registrado y en las que **sí** lo tenían. El
resultado fue **0 unidades frente a 164.349**. La ausencia de precio no señala una semana sin
ventas: señala una semana anterior al inicio del registro de ventas. La regla que se derivó —el
histórico de una serie empieza el día de su primer precio, no antes— quedó codificada en la
capa intermedia del almacén y se acompaña de una comprobación automática que vuelve a
ejecutarse en cada reconstrucción.

### 6.2.2. Los ceros

El **60,1%** de las observaciones diarias válidas es cero —27,7 millones de los 46,1 millones de
días con precio registrado—, y esa fracción no es un defecto del registro sino la característica
dominante del problema. La demanda de una referencia de cola
larga en una tienda concreta es **intermitente**: días sin ninguna venta separados por días con
una o dos unidades. Esto tiene tres consecuencias metodológicas que recorren todo el trabajo.

Primera, las métricas de error relativo —el MAPE en particular— no son aplicables a nivel de
serie, porque el denominador se anula. Se emplean por ello métricas escaladas (§6.6).

Segunda, la distribución de la variable objetivo no es aproximadamente normal ni siquiera
simétrica: es una distribución con masa en cero y cola positiva. Los modelos de aprendizaje
automático se entrenaron con una función de pérdida coherente con esa forma (§6.4.3).

Tercera, la segmentación del catálogo por predictibilidad —la dimensión XYZ del análisis
ABC/XYZ— deja de ser un adorno de gestión y se convierte en una variable de diseño: la política
de reposición aplica métodos distintos según la clase.

### 6.2.3. Eventos del calendario

El fichero de calendario etiqueta días con eventos de cuatro tipos (deportivos, culturales,
nacionales y religiosos). Para cada evento se compararon sus ventas con las del mismo día de la
semana de las dos semanas anteriores y las dos posteriores, y se retuvieron únicamente aquellos
con efecto consistente y de magnitud apreciable.

Solo **Labor Day** superó el criterio: vende un **28 % más** que un lunes normal, en los cinco años
(entre +22 % y +39 %). **SuperBowl** y **Easter** parecían subir entre un 15 % y un 22 % cuando se
comparaban con la media de todos los días, pero caen siempre en domingo, que ya vende un 20 % más
que un día medio. Frente a un domingo normal, SuperBowl vende lo mismo y Easter un 12 % menos: la
subida era del domingo, no del evento. Un cuarto candidato, incorporado inicialmente por expectativa
comercial más que por evidencia, fue **Black Friday**. El examen del histórico no solo no mostró
un pico: en los cinco años, Black Friday vende un **24 % menos** que los viernes de alrededor
(entre −17 % y −29 % según el año). Thanksgiving, la víspera, también vende menos (−28 %), pero
no es día de cierre, así que estos datos no permiten explicar la caída. Se
retiró del conjunto de eventos de pico. La decisión ilustra un criterio que el trabajo aplica de
forma general: un hallazgo que resulta atractivo para la narrativa comercial pero que el dato no
sostiene no entra en el informe.

Siguiendo la recomendación de la tutoría, los eventos se examinaron también **a nivel semanal**:
ventas de la semana del evento y de las semanas vecinas frente a las cuatro semanas previas. El
resultado justifica el cambio de perspectiva: las dos semanas anteriores a Navidad venden un
4-5 % más, mientras que la semana del día 25 cae un 12 % por el cierre; mirar solo el día exacto
pierde el efecto real. Por eso el modelo de predicción incorpora variables de evento semanal
(§6.4.1).

### 6.2.4. Demanda censurada

La limitación más importante del conjunto de datos no es una carencia de columnas sino una
propiedad de la variable objetivo: **`fact_ventas` registra unidades vendidas, no unidades
demandadas**. Cuando un establecimiento se queda sin existencias de una referencia, ese día se
registra un cero que es indistinguible de un día sin demanda. La demanda está, en términos
estadísticos, **censurada por la derecha en el nivel del inventario disponible**, y ese nivel no
se observa.

Las consecuencias recorren todo el trabajo y conviene enunciarlas juntas:

- Los modelos de §7.3 se entrenan sobre demanda censurada, de modo que **predicen por debajo** de
  la demanda verdadera. El sesgo no es uniforme: es mayor precisamente en las series con más
  rotura, que son aquellas en las que acertar importa más.
- La simulación de §7.4 calcula el faltante como la diferencia entre demanda observada y nivel
  objetivo. Pero la demanda observada ya excluye las ventas perdidas por roturas anteriores, de
  modo que la cifra de margen perdido es una **cota inferior** y no una estimación.
- La elasticidad de §7.5 se estima sobre cantidades censuradas, lo que añade una fuente de sesgo
  adicional a la de endogeneidad ya documentada.

Sin datos de inventario el problema **no es corregible**: no existe información que permita
determinar qué ceros correspondieron a rotura. Sí es acotable, y así se trata en §7.4.8: un cero
observado en una serie cuya intensidad esperada hace ese cero improbable es incompatible con
demanda nula, y el conjunto de esos días permite construir cotas para la demanda no observada.

La dirección del sesgo es conocida y favorable a las conclusiones del trabajo: todas las cifras
de coste de rotura presentadas son conservadoras. Esa asimetría se declara explícitamente cada
vez que aparece una de ellas.

### 6.2.5. Días de cierre

Se identificaron los días en los que la venta agregada de una tienda es exactamente cero, que
corresponden a cierres del establecimiento y no a ausencia de demanda. Tratarlos como demanda
nula contamina tanto las medias móviles como el entrenamiento de los modelos. Se marcaron con
una bandera en la dimensión de calendario y se excluyeron de la evaluación; la regla de cierre
aplicada a la previsión tiene un efecto medible que se cuantifica en §7.3.

## 6.3. Arquitectura del almacén analítico

Los primeros análisis se realizaron leyendo directamente los ficheros de origen desde los
cuadernos. Ese esquema deja de funcionar en cuanto hay más de un consumidor: el cuaderno de
predicción, el de reposición, el cuadro de mando y el servicio web acabarían cada uno con su
propia lectura y su propia interpretación de las mismas columnas. La solución adoptada fue
construir un almacén analítico con una única fuente de verdad.

### 6.3.1. Arquitectura medallón

El almacén se organiza en tres capas sucesivas, cada una con una responsabilidad única:

**Bronce.** Copia fiel de los ficheros de origen convertida a formato columnar Parquet, sin
ninguna transformación semántica. Su función es doble: desacoplar el resto del sistema del
formato de entrega de la fuente y reducir el coste de lectura. Los 490,9 MB de CSV pasan a
**22,1 MB** en bronce, una reducción de 22 veces atribuible a la codificación columnar y la
compresión.

**Plata.** Datos limpios y normalizados: el histórico de ventas desplegado a formato largo, los
precios unidos por semana, el calendario resuelto a fechas y las reglas de calidad de §6.2
aplicadas. Ocupa 44,7 MB. Es la capa donde vive la lógica de negocio sobre el dato en bruto y
donde se ejecutan las comprobaciones automáticas de integridad.

**Oro.** Modelo dimensional listo para consumo, con las agregaciones precalculadas. Ocupa
91,0 MB —más que plata, porque incorpora tablas derivadas y agregados— y es la única capa que
leen los consumidores.

> **[FIGURA 6.1]** *Arquitectura del almacén en tres capas.*
> `Fuente: Diagrama de elaboración propia. Vectorial o 200 ppp.`

El despliegue del formato ancho a formato largo, que es la operación más pesada del proceso,
se resuelve con una sola sentencia `UNPIVOT` sobre las 1.913 columnas diarias: **58.327.370
filas en cuatro segundos**. La reconstrucción íntegra del almacén desde los ficheros de origen
tarda aproximadamente **veinte segundos**.

### 6.3.2. Modelo dimensional

La capa oro adopta un **esquema en estrella** con cuatro dimensiones y tres tablas de hechos:

| Tabla | Tipo | Filas | Contenido |
|---|---|---|---|
| `dim_calendario` | dimensión | 1.941 | Fecha, día de la semana, evento, banderas de cierre y temporada |
| `dim_producto` | dimensión | 3.049 | Categoría, departamento y los grupos de §7.2 |
| `dim_tienda` | dimensión | 10 | Nombre y ciudad |
| `dim_serie` | dimensión | 30.490 | Estadísticos de la serie y clases ABC/XYZ |
| `fact_ventas` | hecho | 58.327.370 | Unidades, precio e importe por día |
| `fact_predicciones` | hecho | 853.720 | Previsión media y percentil 90 a 28 días |
| `fact_reposicion` | hecho | 121.960 | Nivel objetivo y pedido sugerido por revisión |

`dim_calendario` incluye 28 días posteriores al último día con venta, marcados con una bandera
de futuro, para que el horizonte de predicción tenga soporte en la dimensión temporal. La
tabla `dim_serie` introduce además una clave sustituta —`serie_id`— que sustituye a la pareja
de identificadores de texto en todas las uniones, lo que reduce de forma apreciable el coste de
las consultas sobre la tabla de 58 millones de filas.

Se añaden dos tablas agregadas de consumo directo, `mart_ventas_dia` (133.910 filas) y
`mart_producto_tienda` (30.490 filas), destinadas al cuadro de mando y a las consultas de nivel
ciudad o departamento, que no necesitan bajar al grano diario.

> **[FIGURA 6.2]** *Modelo dimensional de la capa de consumo (esquema en estrella).*
> `Fuente: Diagrama de elaboración propia con las cuatro dimensiones y las tres tablas de hechos.`

### 6.3.3. Motor y decisiones de implementación

El almacén se implementó sobre **DuckDB**, un motor analítico embebido que ejecuta SQL
directamente sobre ficheros Parquet sin necesidad de servidor. La elección responde a tres
criterios: el volumen —58 millones de filas— es grande para pandas y pequeño para un clúster;
el modelo de ejecución columnar y vectorizado se ajusta a consultas de agregación; y la ausencia
de servidor mantiene el proyecto reproducible en cualquier máquina con un solo comando.

Dos decisiones de implementación merecen mención porque no son evidentes. La primera es que el
motor se instancia **en memoria** y las tablas se materializan como ficheros Parquet, en lugar
de mantener una base de datos persistente en disco; esto evita por completo la gestión del
fichero de registro de escritura anticipada, que en carpetas sincronizadas produce errores de
borrado. La segunda es que el directorio temporal del motor se sitúa fuera del árbol del
proyecto, por la misma razón.

### 6.3.4. La trampa del abanico

Al construir el cuadro de mando se detectó un error de agregación que conviene documentar
porque es sistemático y silencioso. La tabla `fact_ventas` tiene grano diario y
`fact_reposicion` grano semanal; unirlas directamente multiplica por siete cada métrica del
lado semanal. El síntoma fue un stock de seguridad agregado de 2,6 millones de unidades donde
el valor correcto era de aproximadamente 29.000. La solución —agregar cada tabla por separado
en expresiones comunes de tabla y unir después los resultados— quedó documentada en la guía del
cuadro de mando como patrón obligatorio.

## 6.4. Ingeniería de variables

### 6.4.1. Variables construidas

El conjunto de variables predictoras se organiza en cuatro bloques:

- **Retardos.** Valores de la serie en días anteriores, con el retardo mínimo condicionado por
  el horizonte de predicción (§6.4.2).
- **Medias móviles.** Promedios de la serie sobre ventanas de 7, 28, 91 y 364 días.
- **Calendario.** Día de la semana, mes, semana del año, bandera de fin de semana y evento del
  día.
- **Eventos a nivel semanal.** Si la semana (de sábado a viernes, como el calendario original)
  contiene un evento, cuál, cuántos días faltan para el próximo evento y cuántos han pasado desde
  el último. Se conocen de antemano por el calendario, de modo que no introducen información
  futura.
- **Precio y segmento.** Precio de la semana, variación relativa respecto de la semana anterior,
  categoría, departamento, tienda, ciudad y el grupo de producto obtenido en §7.2.

### 6.4.2. La restricción de retardo mínimo

Predecir a veintiocho días vista impone una restricción que se pasa por alto con facilidad: el
día que se predice con horizonte 28 no puede utilizar el valor de la serie del día anterior,
porque en el momento de predecir ese valor todavía no existe. El trabajo resuelve esta
restricción con una **estrategia por bloques semanales**: se entrenan cuatro modelos, uno por
cada semana del horizonte, con retardos mínimos de 7, 14, 21 y 28 días respectivamente. Cada
modelo utiliza toda la información realmente disponible en el momento de predecir su bloque, ni
más ni menos.

La alternativa habitual —la estrategia recursiva, que alimenta el modelo con sus propias
predicciones— se descartó porque acumula el error a lo largo del horizonte. El efecto de esta
elección resultó ser, con diferencia, el factor que más influyó en la precisión final, muy por
encima de la biblioteca de aprendizaje utilizada (§7.3).

### 6.4.3. Función de pérdida

Los modelos de aprendizaje automático se entrenaron con la función de pérdida **Tweedie** con
parámetro de potencia de varianza 1,1. La distribución de Tweedie en ese rango es una
compuesta Poisson-Gamma: describe una variable con masa de probabilidad en cero y cola positiva
continua, que es exactamente la forma de la demanda diaria intermitente. Entrenar con error
cuadrático sobre esta variable equivale a suponer una distribución normal y produce
predicciones sistemáticamente desplazadas hacia arriba en las series con muchos ceros.

### 6.4.4. Precisión numérica

Se documenta aquí una limitación técnica encontrada durante el trabajo por su efecto práctico.
La construcción del conjunto de entrenamiento a partir de un `DataFrame` de pandas provoca en
LightGBM una conversión interna a doble precisión que duplica la memoria requerida y agota la
disponible en el equipo de trabajo. La conversión explícita previa a matrices `float32` resuelve
el problema sin pérdida apreciable de precisión, dado el rango de las variables.

## 6.5. Protocolo de validación

### 6.5.1. Validación temporal por avance

Toda la evaluación de modelos de predicción emplea **validación walk-forward** con tres
pliegues. Cada pliegue entrena con una ventana de días anterior a una fecha de corte y evalúa
sobre los veintiocho días siguientes; la fecha de corte avanza en el tiempo entre pliegues. No
se emplea en ningún momento validación cruzada aleatoria: barajar observaciones de una serie
temporal permite al modelo entrenar con el futuro y produce estimaciones de error
optimistas que no se reproducen en explotación.

Los tres pliegues cumplen además una función de diagnóstico: la dispersión del error entre
pliegues informa sobre la estabilidad del modelo. En este trabajo esa dispersión resultó ser
relevante en un caso concreto —el sesgo de la predicción, que no se mantuvo constante entre
pliegues— y condicionó la decisión de calibrar únicamente con la ventana más reciente (§7.3).

> **[FIGURA 6.3]** *Esquema de la validación temporal por avance.*
> `Fuente: Diagrama de elaboración propia: tres ventanas de entrenamiento y sus horizontes de 28 días.`

### 6.5.2. Ventana de entrenamiento

La comparación de modelos de §7.3 se hizo con ventanas de 180 días, con el argumento de que la
media móvil anual ya aporta la referencia estacional. Ese argumento resultó insuficiente: con 180
días, el modelo que predice diciembre no ha visto ninguna Navidad, y la media anual no basta para
que aprenda el cierre del día 25 ni la subida de las semanas previas. Se repitió la validación
con **400 días**, que incluyen el año anterior completo: el error mejora un 5,7 % en diciembre y
un 3,4 % en noviembre sin empeorar el resto del año. El **modelo final se entrena con 400 días**;
el coste es un tiempo de entrenamiento algo más del doble.

### 6.5.3. Validación de la segmentación

La segmentación de productos se validó en tres pasos. Las **variables** se revisaron con su
matriz de correlación, para descartar las que repetían información. El **número de grupos** se
eligió con el método del codo —*k*-medias con *K* de 2 a 14— y el coeficiente de silueta. La
**estabilidad** se comprobó repitiendo la segmentación con diez semillas aleatorias y midiendo
con el índice de Rand ajustado la coincidencia con la primera ejecución.

Las tiendas no se segmentaron con un algoritmo: con diez tiendas y unas doce variables de
perfil, se compararon directamente mediante una tabla de perfil y una matriz de distancias
(§7.2.4).

## 6.6. Métricas

### 6.6.1. Error de predicción

Se emplean cuatro métricas, cada una para un propósito distinto.

**MAE y RMSE** describen el error en unidades de la variable. Son interpretables pero no
agregables entre series de escalas muy distintas: el error de una referencia que vende
doscientas unidades diarias domina cualquier promedio en el que participe una que vende dos.

**RMSSE** (*root mean squared scaled error*) resuelve ese problema escalando el error cuadrático
medio por el error que cometería, dentro del propio período de entrenamiento, la predicción
ingenua de un paso: predecir cada día con el valor del día anterior.

$$\text{RMSSE} = \sqrt{\dfrac{\frac{1}{h}\sum_{t=n+1}^{n+h}(y_t-\hat{y}_t)^2}{\frac{1}{n-1}\sum_{t=2}^{n}(y_t-y_{t-1})^2}}$$

El denominador convierte la métrica en adimensional y permite promediar entre las 30.490 series.
Conviene leerlo con cuidado: la referencia predice *un día* vista con el dato de ayer, un
problema más fácil que predecir a 28 días, de modo que un RMSSE ligeramente superior a 1 no
significa que el modelo sea peor que una regla ingenua aplicada al mismo horizonte. Lo que
importa es la comparación entre modelos y referencias con la misma métrica.

**WRMSSE** pondera el RMSSE de cada serie por su participación en la facturación. Es la métrica
principal del trabajo, porque una mejora del error en una referencia que factura mil dólares
diarios y otra en una que factura dos no tienen el mismo valor para la compañía.

**WAPE semanal** (*weighted absolute percentage error*) responde a una observación de la
tutoría: más de la mitad de los días-producto no tienen ninguna venta, y medir el error día a día
mezcla el error del modelo con el azar de qué día concreto cae cada venta. Se suman predicción y
venta real de cada serie por semanas y se calcula

$$\text{WAPE} = \frac{\sum |\hat{y} - y|}{\sum y} \times 100$$

que se lee directamente como el porcentaje de las unidades de la semana en que se equivoca el
modelo. No falla con los ceros, porque divide por el total vendido, y coincide con el horizonte
de la reposición, que también es semanal. El WRMSSE se mantiene para comparar modelos; el WAPE
semanal, para explicar el error a negocio.

**Pérdida pinball** evalúa las predicciones cuantílicas. Para un cuantil $\tau$ y un error
$e = y - \hat{q}_\tau$:

$$L_\tau(e) = \max\big(\tau e,\ (\tau-1)e\big)$$

La asimetría de la función es lo que hace que su minimización devuelva el cuantil buscado y no
la media: con $\tau = 0{,}9$, quedarse corto penaliza nueve veces más que pasarse.

Se acompaña de la **cobertura empírica**: la proporción de observaciones reales que no superan
el percentil predicho. Una cobertura del 90% frente a un objetivo del 90% indica un intervalo
bien calibrado.

### 6.6.2. Métricas de segmentación

La **inercia** es la suma de las distancias al cuadrado de cada elemento al centro de su grupo.
Disminuye siempre al aumentar el número de grupos; el **codo** de su curva señala el punto a
partir del cual añadir grupos apenas reduce la dispersión. Cuando la curva es suave, el codo se
localiza como el punto más alejado de la recta que une sus extremos.

El **coeficiente de silueta** compara, para cada elemento, su distancia media al propio grupo
con la distancia media al grupo vecino más próximo; toma valores en $[-1, 1]$ y se usa como
criterio de apoyo dentro de la zona del codo.

El **índice de Rand ajustado** mide la concordancia entre dos particiones del mismo conjunto
corrigiendo por la coincidencia esperable al azar; aquí se emplea para medir la estabilidad de
la segmentación entre ejecuciones con distinta semilla.

### 6.6.3. Métricas económicas

La evaluación de la política de reposición abandona las métricas de error y se expresa en
dinero. Se distinguen tres componentes de coste sobre el horizonte simulado:

- **Margen perdido por rotura**, calculado como las unidades de demanda no atendida
  multiplicadas por el margen unitario.
- **Coste de mantenimiento**, proporcional al inventario medio inmovilizado.
- **Merma**, proporcional al remanente no vendido al final del ciclo.

El **nivel de servicio** se mide como la proporción de unidades de demanda atendidas sobre la
demanda total, y no como la proporción de ciclos sin rotura, que es una definición más
benévola.

## 6.7. Reproducibilidad

Todo el trabajo se ejecuta desde el almacén analítico y no desde ficheros temporales, de modo
que borrar cualquier caché no impide reproducir ningún resultado. Los cinco cuadernos se
generan a partir de guiones de construcción versionados —no se editan a mano—, lo que garantiza
que el cuaderno entregado y el código que lo produce no puedan divergir. Las semillas
aleatorias están fijadas en todos los procedimientos con componente estocástica.

El entorno de ejecución y los tiempos de referencia de cada etapa se detallan en el anexo, junto
con el procedimiento completo de reconstrucción desde los ficheros de origen.
