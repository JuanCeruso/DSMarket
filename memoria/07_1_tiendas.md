# 7. Resultados y conclusiones

## 7.1. Qué está pasando en las tiendas

> «Mirá en profundidad cómo se está vendiendo.»
> — Michelle Huggins, directora de datos de DSMarket

La primera petición del encargo no plantea un problema de modelado sino de descripción. Antes de
predecir nada conviene saber si la demanda de DSMarket es una sola cosa o varias, porque de esa
respuesta depende que tenga sentido tratar la cadena como un único sistema o haga falta
segmentarla. El análisis exploratorio se organizó, por tanto, alrededor de una pregunta
concreta: **¿hasta qué punto se parecen entre sí las diez tiendas?**

### 7.1.1. La estructura temporal

La serie agregada de la cadena muestra los tres componentes esperables en un minorista de
gran consumo. Una **tendencia** suavemente creciente a lo largo de los cinco años. Una
**estacionalidad semanal** marcada, con el fin de semana por encima de la media y el punto bajo
a mitad de semana. Y una **estacionalidad anual** con máximo en verano y un comportamiento
particular en diciembre, que resulta ser el mes con mayor dispersión entre productos: no es que
diciembre venda más de todo, es que vende mucho más de unas pocas referencias.

Los días de cierre de establecimiento aparecen con claridad como ceros exactos en la venta
agregada de una tienda. Se identificaron y se marcaron, y su tratamiento tiene consecuencias
que se cuantifican en §7.3.

![**Figura 7.1.** Serie agregada de ventas diarias, con su tendencia y sus perfiles semanal y anual. *Fuente: elaboración propia a partir de `fact_ventas`.*](figuras/fig_7_1.png){width=100%}

### 7.1.2. Los eventos que importan y el que no

De los eventos del calendario, solo uno muestra un pico consistente una vez comparado con el
mismo día de la semana: **Labor Day**, que vende un **28 % más** que un lunes normal en los cinco
años. **SuperBowl** y **Easter** parecían subir entre un 15 % y un 22 % sobre la venta media, pero
caen siempre en domingo, el día de más ventas: frente a un domingo normal, SuperBowl vende lo mismo
y Easter un 12 % menos. Todos los eventos del calendario, más Christmas y Labor Day, se
incorporaron como variables al conjunto de predictores.

Un cuarto candidato quedó fuera, y merece un párrafo porque la decisión de excluirlo es un
resultado. **Black Friday** se había incorporado inicialmente al análisis por expectativa
comercial: es la fecha que cualquier informe de minorista destaca. El histórico de DSMarket no
muestra ningún pico: Black Friday vende un 24 % menos que los viernes de alrededor (entre −17 % y
−29 % según el año); Thanksgiving, la víspera, también vende menos, pero no cierra (§6.2.3). La tentación de presentarlo como una
oportunidad comercial desaprovechada —«la cadena no está capturando el efecto Black Friday»— era
considerable y habría dado un titular atractivo. El dato no la sostenía, y se retiró del
conjunto de eventos relevantes. Que la ausencia de pico se deba a la política comercial de la
compañía, a la naturaleza de su catálogo o a la codificación del calendario es una pregunta que
estos datos no permiten responder, y así se deja consignado.

![**Figura 7.2.** Coeficiente de elevación por evento del calendario, con Black Friday señalado. *Fuente: elaboración propia a partir de `fact_ventas`.*](figuras/fig_7_2.png){width=100%}

### 7.1.3. Las tiendas no son intercambiables

El hallazgo que sostiene el capítulo procede de una comparación deliberadamente simple. Para
cada ciudad se extrajeron los quince productos más vendidos y se examinó cuántos de ellos son
comunes a las tres.

**Solo cinco de quince.** Los otros diez, dos tercios del top, no figuran a la vez entre los más vendidos de las tres ciudades. La misma comparación entre las tiendas de cada ciudad hace el
contraste más nítido:

| Ciudad | Productos del top 15 comunes a todas las tiendas de la ciudad |
|---|---|
| Boston | 10 de 15 (67 %) |
| Nueva York | 8 de 15 (53 %) |
| **Filadelfia** | **4 de 15 (27 %)** |

Filadelfia es el caso extremo: sus tres tiendas solo comparten cuatro de sus quince referencias
más vendidas. Es la ciudad con las tiendas más distintas entre sí, mientras que las de Boston se
parecen mucho. Este hecho tiene consecuencias directas sobre el diseño de campañas —una promoción
uniforme para toda la red desperdicia esfuerzo en dos tercios de los productos más vendidos— y sobre el
modelado, que es lo que abre el capítulo siguiente.

![**Figura 7.3.** Solapamiento de los quince productos más vendidos entre las tres ciudades. *Fuente: elaboración propia a partir de `fact_ventas`.*](figuras/fig_7_3.png){width=100%}

### 7.1.4. El precio, y un resultado contraintuitivo

El análisis de la dispersión de precios entre tiendas para una misma referencia buscaba
localizar dónde la compañía practica precios diferenciados. La expectativa razonable era
encontrarla en artículos de valor unitario alto, donde unos céntimos de diferencia son irrelevantes y unos dólares no lo son.

El resultado fue el contrario. La categoría con mayor dispersión relativa de precios entre
establecimientos es **SUPERMARKET, con un 2,75%**: un mismo producto es, en mediana, un 2,75 % más caro en la tienda más cara que en la más barata, por delante de ACCESORIES (1,18 %) y HOME_&_GARDEN (0,97 %), de mayor precio unitario. La lectura más plausible es que la diferenciación se concentra donde hay
volumen y competencia local, no donde hay margen unitario; pero el dato disponible permite
constatar el hecho, no explicarlo.

![**Figura 7.4.** Dispersión relativa de precios entre tiendas, por categoría. *Fuente: elaboración propia a partir de `fact_ventas`.*](figuras/fig_7_4.png){width=100%}

Este resultado condiciona el capítulo §7.5: si el precio se mueve, hay algo que estimar. La
pregunta de si ese movimiento permite identificar un efecto causal se responde allí, y la
respuesta no es la esperable.

### 7.1.5. Qué abre el capítulo siguiente

El análisis exploratorio deja establecido que la demanda de DSMarket no es homogénea: varía
entre ciudades, varía entre tiendas de una misma ciudad y varía entre productos de una misma
categoría. Tratar la cadena como una sola serie ignoraría esa estructura, y un modelo por serie —30.490 modelos— sería inmanejable y desaprovecharía la información compartida entre series parecidas. El trabajo responde con un modelo global que aprende de todas las series a la vez (§7.3).

Antes, conviene ordenar esa heterogeneidad agrupando los productos que se venden de forma parecida, que es lo que necesita el diseño de campañas. Ese es el objeto del capítulo siguiente.
