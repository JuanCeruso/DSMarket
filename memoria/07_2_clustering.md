## 7.2. Cómo se comportan los productos y las tiendas

> «Necesitamos agrupar productos que se comporten de forma parecida, para poder evaluar campañas
> sobre grupos y no sobre referencias sueltas.»
> — Joelle, área de marketing

El capítulo anterior estableció que la demanda no es homogénea. Este construye una segmentación
de productos que recoja esa heterogeneidad, con tres requisitos: que el número de grupos se
justifique con un criterio objetivo, que la partición sea estable y que cada grupo admita una
lectura de negocio. Responde además a la segunda pregunta del encargo, si tiene sentido agrupar
también las tiendas.

### 7.2.1. Qué se agrupa y con qué variables

La segmentación se realiza sobre el **comportamiento de venta**, no sobre los atributos del
producto. Dos referencias de departamentos distintos que se venden igual pertenecen al mismo
grupo; dos del mismo departamento que se venden de forma distinta, no. La categoría y el
departamento se reservan para describir los grupos una vez formados.

Se partió de ocho variables candidatas por producto, calculadas sobre la suma de las diez tiendas:
venta diaria media (en logaritmo), coeficiente de variación diario, proporción de días sin venta,
elevación en fin de semana, elevación en diciembre, elevación en días de evento con pico
confirmado (SuperBowl, Easter y Labor Day), tendencia y precio medio.

**Todas se miden desde la primera venta de cada producto.** El 17,8 % de los días-producto son
anteriores a esa primera venta: el producto aún no estaba en el catálogo. Contarlos como «días sin
venta» confundiría un lanzamiento tardío con un producto de compra ocasional. En una primera versión
del análisis se contaban así, y el efecto era visible: la tendencia y la proporción de días sin
venta tenían una correlación de 0,81, porque las dos medían sobre todo cuándo había llegado el
producto. Medidas desde el lanzamiento, esa correlación desaparece (0,10).

La revisión de correlaciones obligó a descartar dos variables. El coeficiente de variación y la
proporción de días sin venta tienen una correlación de **0,89**: un producto que muchos días no
vende es, por fuerza, un producto que vende a saltos, y con las dos dentro la misma idea pesaría
doble en la distancia. La tendencia se descartó por otro motivo: describe el ciclo de vida del
producto, no cuándo y cómo se compra, que es lo que necesita el diseño de campañas; la tendencia ya
la recoge el modelo de predicción con sus medias móviles. La segmentación final usa **seis
variables**: venta diaria, proporción de días sin venta, fin de semana, diciembre, eventos y
precio.

Las variables se estandarizaron con `StandardScaler`. Se probó también `RobustScaler`, que reduce la
influencia de los valores extremos en el cálculo de la escala, pero tiene el efecto contrario sobre
la segmentación: deja los valores extremos aún más alejados y, a partir de ocho grupos, *k*-medias
los aísla en grupos de un solo producto.

### 7.2.2. Elección del número de grupos

El número de grupos se eligió con el **método del codo**: se entrenó *k*-medias con *K* entre 2 y
14 y se registró la inercia de cada partición. La curva es suave, sin un quiebre visible, como es
habitual cuando los productos se reparten de forma continua. Para localizar el codo de forma
objetiva se midió qué puntos de la curva se alejan más de la recta que une sus extremos: la zona
del codo va de **6 a 8 grupos**, y dentro de ella **K = 6** tiene la mejor silueta (0,167).

La silueta es más alta con dos, tres o cuatro grupos, pero esas particiones solo separan productos
de mucha y de poca venta y no distinguen el fin de semana, la Navidad o los eventos, que es lo que
el encargo necesita. La silueta moderada se explica por la misma razón: los grupos tienen bordes
difusos porque los productos forman un continuo.

La estabilidad se comprobó repitiendo la segmentación con diez semillas aleatorias distintas: el
índice de Rand ajustado medio respecto a la primera ejecución es **0,98** (mínimo 0,96). La
partición no depende del punto de partida del algoritmo.

> **[FIGURA 7.5]** *Método del codo: inercia y silueta frente al número de grupos, con la zona del codo y K = 6 señalados.*
> `Fuente: Cuaderno 02, sección 4.4.`

**Respuesta a la pregunta de marketing.** El encargo planteaba 5, 10 o 20 grupos. Con 5, el grupo
de Navidad se diluye dentro de otro mayor. Con 10, la silueta empeora (0,145) y los grupos grandes
de alimentación y hogar se parten en subgrupos que solo se diferencian en matices. Con 20, uno de
los grupos contiene un único producto. Seis grupos es la partición que el método justifica y la
más manejable para planificar campañas. Trabajar con una única segmentación evita además
mantener dos clasificaciones del mismo producto que no encajan entre sí.

### 7.2.3. Los seis grupos de producto

Cada grupo se resume en una ficha con su tamaño, los valores medios de las variables y dos
variables que no intervinieron en la segmentación: la composición por categoría y el peso en la
facturación. Con ellas se asignó a cada grupo un nombre que dice qué productos contiene. Cuando una
categoría es mayoritaria, aparece en el nombre; cuando el grupo es mixto, se nombra por el momento
de compra.

| Grupo | Productos | % facturación | Rasgo que lo define |
|---|---|---|---|
| **Alimentación de consumo diario** | 679 | 42,4 % | 72 % alimentación, el precio más bajo (2,6 $). Venta muy alta (37 unidades al día entre las diez tiendas) y casi diaria: 5 % de días sin venta. |
| **Hogar de fin de semana** | 882 | 25,4 % | 45 % hogar y jardín. La mayor elevación en fin de semana (+42 %), y también sube en los eventos. |
| **Básicos de rotación lenta** | 745 | 14,7 % | Mixto. Venta baja (6 unidades al día) y sin picos: los que menos reaccionan al fin de semana, a diciembre y a los eventos. |
| **Accesorios y hogar de precio alto** | 218 | 11,1 % | 48 % accesorios y 43 % hogar. Precio medio de 17,4 $, más del triple que el resto. |
| **Compra ocasional en fechas señaladas** | 405 | 4,2 % | Mixto. No venden nada en el 39 % de los días en que están a la venta, pero venden un 26 % más en los días de evento. |
| **Temporada de Navidad** | 120 | 2,1 % | Mixto (accesorios, alimentación y hogar: mesa y regalo). Venden casi el doble en diciembre (1,89 veces). |

Los dos primeros grupos reúnen el 68 % de la facturación. La compra ocasional ocupa el 13 % del
catálogo y aporta el 4 %: es el grupo donde la pregunta pertinente no es solo cuánto reponer sino
si mantener la referencia.

> **[FIGURA 7.6]** *Proyección PCA de los productos coloreados por grupo, y peso de cada grupo en el catálogo y en la facturación.*
> `Fuente: Cuaderno 02, sección 4.6.`

Dentro del grupo de Navidad destaca **`SUPERMARKET_3_069`**, con una elevación en diciembre de
**7,66**, la mayor del catálogo. Sus cuatro mejores días en cinco años son cuatro 31 de diciembre
consecutivos: se trata, con toda probabilidad, de un artículo de Nochevieja. El caso ilustra un
límite del enfoque predictivo que se desarrolla en §7.3: un modelo entrenado sobre una ventana de
180 días nunca ve un 31 de diciembre cuando predice diciembre. Por eso el modelo final se entrena
con 400 días de historia, de forma que vea al menos un ejemplo de cada fecha señalada.

> **[FIGURA 7.7]** *Serie diaria de SUPERMARKET_3_069 con sus mejores días señalados.*
> `Fuente: Cuaderno 02, sección 4.8.`

### 7.2.4. Las tiendas: comparación directa en lugar de agrupamiento

El encargo preguntaba también si tendría sentido agrupar las tiendas. **Con estos datos, no
mediante un algoritmo.** Son solo diez tiendas, y describir su perfil de demanda requiere en torno
a doce variables (volumen, estabilidad, fin de semana, diciembre, nivel de precio y el peso de cada
departamento). Con más dimensiones que observaciones, las distancias pierden capacidad de
discriminar —la maldición de la dimensionalidad— y cualquier agrupación resultante depende de qué
tiendas entren en el cálculo. Diez elementos, además, se comparan mejor directamente.

Las tiendas se compararon con una tabla de perfil, un mapa de calor de desviaciones respecto a la
media y una matriz de distancias calculada sobre las variables de perfil (variabilidad, fin de
semana, diciembre, índice de precio y peso de alimentación y hogar). El volumen se dejó fuera de la
distancia porque mide el tamaño de la tienda, no su forma de vender.

La comparación arroja tres resultados:

- **Tribeca, en Nueva York, se parece más a las tiendas de Boston que a las de su ciudad.** Sus
  dos tiendas más parecidas son Back Bay y South End. Comparte con ellas un precio por debajo de la
  media (−0,39 %, frente a valores de entre −0,55 % y −0,85 % en Boston y de +0,36 % a +0,40 % en el
  resto de Nueva York), baja variabilidad diaria y un fin de semana moderado.
- **Las tres tiendas de Boston forman el conjunto más homogéneo**, coherente con lo observado en
  §7.1 sobre los productos más vendidos.
- **Harlem y Midtown Village no se parecen a ninguna otra tienda.** Harlem tiene la mayor
  elevación de fin de semana (+50 %) y el mayor peso de hogar; Midtown Village es la única tienda
  que vende más en diciembre que el resto del año y, junto con Yorktown, la de venta más irregular.

La lectura de negocio es que el perfil de una tienda depende más de su entorno —el tipo de barrio,
la clientela— que de su ciudad. Para una apertura, la referencia de surtido y de previsión inicial
debería ser la tienda existente más parecida en tipo de barrio, no la media de su ciudad.

> **[FIGURA 7.8]** *Perfil de cada tienda respecto a la media y matriz de parecido entre tiendas.*
> `Fuente: Cuaderno 02, secciones 5.2 y 5.3.`

### 7.2.5. Segmentación operativa ABC/XYZ

Además de la segmentación por comportamiento, se construyó la clasificación **ABC/XYZ** que
utiliza la política de reposición del capítulo §7.4. La dimensión ABC ordena las series por
facturación acumulada; la dimensión XYZ, por predictibilidad, medida con el coeficiente de
variación de la demanda diaria.

La matriz resultante concentra la información de gestión en una sola tabla: la celda **AX**
—alta facturación, demanda estable— reúne alrededor del **56 % de la facturación** de la cadena,
y es donde la automatización de la reposición rinde más. En el extremo opuesto, la celda **CZ**
representa cerca del **28 % del catálogo** por apenas el **3,5 % de la facturación**: series
erráticas donde, además de cuánto reponer, la pregunta pertinente es si mantener la referencia.

Las dos segmentaciones responden a preguntas distintas y se complementan: el grupo de
comportamiento dice *cómo* se vende un producto (diario, fin de semana, Navidad, eventos), y la
clase XYZ dice *cuánto se puede fiar* la previsión de cada serie. En los extremos cuentan casi la
misma historia —la alimentación de consumo diario es el único grupo con mayoría de series estables
(53 % X) y la compra ocasional es casi toda errática (77 % Z)—, y en el medio se complementan.

> **[FIGURA 7.9]** *Matriz ABC/XYZ: recuento de series y peso en la facturación.*
> `Fuente: Cuaderno 04. Dos mapas de calor 3x3 con los valores impresos.`

### 7.2.6. Una hipótesis que no sobrevivió: la afinidad entre productos

La segmentación por comportamiento sugiere una pregunta natural que el encargo no formulaba:
si hay productos que se comportan igual, ¿los hay que se compran juntos? La respuesta a esa
pregunta habilitaría recomendaciones de venta cruzada y promociones conjuntas.

**Lo primero que hubo que establecer es que el dato no permite responderla como se suele.** El
registro de ventas viene agregado por producto, tienda y día: no hay ticket, ni transacción, ni
cliente. Un análisis de cesta de la compra —soporte, confianza, lift, reglas de asociación—
necesita la cesta, y la cesta no está. Presentar cualquier resultado como «estos productos se
compran juntos» sería una afirmación que el dato no sostiene.

Lo que sí puede medirse es la **afinidad de demanda**: productos cuya venta sube y baja los
mismos días en el mismo establecimiento. Y tiene una trampa que invalida la versión ingenua,
porque casi todo el co-movimiento diario lo explica algo compartido —el día de la semana, el
mes, un evento, el tráfico de la tienda—. Se aplicó por tanto el mismo procedimiento que en
§7.5: residualizar cada serie contra esos factores y medir el co-movimiento sobre lo que queda.

La residualización funcionó: la correlación media entre pares cae de **+0,041 a +0,001**, y la
proporción de pares con correlación superior a 0,30 pasa del **5,17 % al 2,55 %**. Buena parte de
la asociación aparente era, en efecto, calendario.

**La prueba que decide.** Un producto de una tienda y otro de una tienda distinta no pueden
compartir cesta por construcción, de modo que la distribución de sus correlaciones residuales es
el nivel de ruido. Sobre 14.280 pares entre establecimientos distintos, el percentil 99 se sitúa
en **+0,3875**: pares que físicamente no pueden estar relacionados alcanzan correlaciones de
casi 0,4. De los pares del mismo establecimiento, solo el **1,27 %** supera ese umbral, frente al
1,00 % esperable por azar.

**No hay señal.** El exceso es indistinguible del ruido. Las parejas mejor clasificadas lo
parecen, pero al desplazar una de las dos series un solo día la correlación apenas cae —nitidez
mediana de 0,063—, lo que indica tendencia compartida y no compra simultánea.

La conclusión práctica para DSMarket es concreta: el dato que permitiría responder esta pregunta
es el **identificador de ticket** en el registro de ventas, y hoy no existe. Es la tercera
recomendación de incorporación de datos de este trabajo, después de la merma y el inventario.

### 7.2.7. Qué abre el capítulo siguiente

Con los productos segmentados y la clasificación operativa construida, el trabajo dispone de la
estructura necesaria para modelar. El grupo de producto entra como variable en el modelo de
predicción, y la clasificación ABC/XYZ, junto con el grupo, determina más adelante qué método de
reposición se aplica a cada serie.

La pregunta siguiente es la que el encargo formula de forma más directa: cuánto se va a vender.
