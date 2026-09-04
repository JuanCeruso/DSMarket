## 7.2. Cómo se comportan los productos y las tiendas

> «Necesitamos agrupar productos que se comporten de forma parecida, para poder evaluar
> campañas sobre grupos y no sobre referencias sueltas.»
> — Joelle, área de marketing

El capítulo anterior estableció que la demanda no es homogénea. Este construye las agrupaciones
que capturan esa heterogeneidad, con dos requisitos: que sean estables —que no dependan de qué
tiendas concretas entran en el cálculo— y que admitan una lectura de negocio.

### 7.2.1. Qué se agrupa y con qué variables

La segmentación se realiza sobre el **perfil de demanda**, no sobre los atributos del producto.
Dos referencias de departamentos distintos que se venden igual pertenecen al mismo grupo; dos
referencias del mismo departamento que se venden de forma distinta, no. Esto es lo que hace la
segmentación útil para diseñar campañas: agrupa por comportamiento, que es lo que una campaña
puede mover, y no por catálogo, que ya está en la ficha del producto.

El vector que describe cada producto reúne cuatro bloques:

- **Perfil semanal**: la distribución de la venta entre los siete días de la semana, normalizada.
- **Perfil mensual**: la distribución entre los doce meses, normalizada, que captura la
  estacionalidad.
- **Elevación en diciembre** (`dec_lift`): el cociente entre la venta media de diciembre y la
  venta media anual.
- **Elevación en eventos** (`event_lift`): el mismo cociente para los días con evento relevante.

Las dos últimas variables se añadieron precisamente para que la segmentación pudiera distinguir
comportamientos de campaña, que era la finalidad del encargo.

**Limitación reconocida.** Los perfiles semanal y mensual son datos composicionales: sus
componentes suman uno por construcción, de modo que operar sobre ellos con distancia euclídea
—como hace *k*-medias— no respeta la geometría del símplex en el que viven. El tratamiento
riguroso pasaría por una transformación logarítmica de razones antes de agrupar. No se aplicó,
y se consigna como limitación metodológica; los resultados de estabilidad de §7.2.5 sugieren que
el efecto práctico sobre esta partición concreta es menor, pero eso es evidencia indirecta y no
una demostración.

### 7.2.2. Elección del número de grupos

Se aplicó *k*-medias sobre el vector normalizado, explorando el número de grupos entre 2 y 12 y
evaluando cada partición con las tres métricas internas descritas en §6.6.2. El coeficiente de
silueta desciende de forma monótona con el número de grupos, como es habitual, de modo que la
decisión no puede tomarse solo con él. El criterio combinado —silueta aceptable, mínimo local
del índice de Davies-Bouldin y máximo relativo del de Calinski-Harabasz— apuntó a **K = 5** como
partición gruesa.

Se retuvo además una partición fina de **K = 10** con un propósito distinto y explícito: la
partición de cinco grupos responde a la pregunta «¿cómo se comporta este producto?», y la de
diez responde a «¿sobre qué grupo lanzo esta campaña?». No compiten; se usan para cosas
distintas y ambas se publican en la dimensión de producto del almacén.

Como comprobación de que la estructura encontrada no es un artefacto del método, la misma
partición se obtuvo con agrupamiento jerárquico de Ward y con un **modelo de mezclas
gaussianas**. La concordancia entre las tres, medida con el índice de Rand ajustado, resultó
alta y sostiene que los grupos describen una estructura presente en los datos y no una
imposición del algoritmo. El modelo de mezclas aporta además una lectura que *k*-medias no da:
la pertenencia probabilística permite identificar los productos que quedan a caballo entre dos
arquetipos, que son precisamente los que una campaña dirigida debería tratar con cuidado.

> **[FIGURA 7.5]** *Métricas internas de agrupamiento frente al número de grupos.*
> `Fuente: Cuaderno 02. Tres paneles: silueta, Davies-Bouldin y Calinski-Harabasz, con K=5 señalado.`

### 7.2.3. Los cinco arquetipos de producto

Los cinco grupos admiten una interpretación directa en términos de comportamiento comercial. Se
describen aquí por su perfil característico y no por su composición de catálogo, que es
heterogénea en todos ellos, lo que confirma que la agrupación por comportamiento no reproduce la
agrupación por departamento.

| Arquetipo | Referencias | Rasgo que lo define |
|---|---|---|
| **Núcleo estable** | 948 | Perfil semanal plano y estacionalidad apagada. Concentra la mayor parte de la facturación y es el que mejor se predice. |
| **Fin de semana/hogar** | 859 | Venta concentrada en sábado y domingo. |
| **Fin de año** | 569 | Elevación marcada en diciembre. |
| **Cola larga/eventos** | 484 | Demanda esporádica, muchos días sin venta, reacción a fechas señaladas. |
| **Premium/accesorios** | 189 | El grupo más pequeño, de mayor precio unitario y rotación baja. |

El grupo de **Núcleo estable** es el que sostiene la facturación y el que la previsión acierta con
holgura; el de **Cola larga/eventos** es el que la política de reposición tratará de forma
distinta en §7.4. El de **Fin de año** es donde aparece el caso descrito a continuación.

> **[FIGURA 7.6]** *Perfil semanal y mensual medio de los cinco arquetipos de producto.*
> `Fuente: Cuaderno 02. Rejilla de cinco filas con dos paneles cada una.`

### 7.2.4. Lo que la partición fina revela y la gruesa disuelve

Al pasar de cinco a diez grupos aparecen dos micro-segmentos que en la partición gruesa quedaban
absorbidos y que son exactamente los que interesan para campañas:

- Un **segmento navideño**, con una elevación en diciembre de **2,29** veces la media anual.
- Un **segmento de eventos**, con una elevación en fechas señaladas de **1,99**.

Ambos reaparecen en los capítulos siguientes: son los segmentos donde la predicción falla en
temporada alta (§7.3) y donde la política de reposición necesita un nivel de servicio distinto
(§7.4).

Dentro del segmento navideño, un producto se separa del resto de forma llamativa:
**`SUPERMARKET_3_069`**, con una elevación en diciembre de **7,66**. La inspección de sus días
de máxima venta muestra que los cuatro primeros son cuatro 31 de diciembre consecutivos. Se
trata, con toda probabilidad, de un artículo de Nochevieja. El caso se destaca porque ilustra
un límite del enfoque adoptado: un modelo entrenado sobre una ventana de 180 días nunca ve un
31 de diciembre cuando predice noviembre, y por tanto no puede anticipar ese pico. La solución
para productos así no es un modelo mejor, es una regla de calendario.

> **[FIGURA 7.7]** *Serie diaria de SUPERMARKET_3_069 con los cuatro 31 de diciembre señalados.*
> `Fuente: Cuaderno 02. Es la figura que hace evidente el argumento del párrafo siguiente.`

### 7.2.5. Las tiendas, y un hallazgo que cruza fronteras

La misma metodología aplicada a las diez tiendas —sobre su perfil de demanda por categoría, día
de la semana y mes— produce **tres grupos de comportamiento**. El resultado interesante es que
**esos grupos no coinciden con las ciudades**:

| Grupo | Tiendas | Ciudades que mezcla |
|---|---|---|
| A | Greenwich Village, Brooklyn, Queen Village, Yorktown | Nueva York y Filadelfia |
| B | Harlem, Midtown Village | Nueva York y Filadelfia |
| **C** | **South End, Roxbury, Back Bay, Tribeca** | **Boston y Nueva York** |

El grupo C reúne los tres establecimientos de Boston con **Tribeca**, en Nueva York. Ninguno de
los tres grupos respeta la frontera de ciudad.

Un resultado así invita a la sospecha, porque es el tipo de hallazgo que puede deberse a la
inestabilidad del algoritmo con solo diez observaciones. Se sometió por ello a una validación
por exclusión sucesiva: se repitió la segmentación diez veces, eliminando cada vez una tienda
distinta, y se midió con el índice de Jaccard cuánto se conservaba cada grupo. **El grupo que
reúne a las tiendas de Boston con Tribeca se mantuvo unido en las diez iteraciones**, con
similitud de Jaccard igual a 1 en todos los casos.

La lectura de negocio es que el perfil de demanda de una tienda lo determina su entorno —el tipo
de barrio, la clientela, la competencia próxima— más que su ciudad administrativa. Para el
diseño de campañas eso significa que la unidad de segmentación geográfica no debería ser la
ciudad.

> **[FIGURA 7.8]** *Grupos de tienda y estabilidad en la validación por exclusión sucesiva.*
> `Fuente: Cuaderno 02. Proyección de las diez tiendas con el color del grupo, y tabla de Jaccard.`

### 7.2.6. Segmentación operativa ABC/XYZ

Además de la segmentación por comportamiento, se construyó la clasificación **ABC/XYZ** que
utiliza la política de reposición del capítulo §7.4. La dimensión ABC ordena las series por
facturación acumulada; la dimensión XYZ, por predictibilidad, medida con el coeficiente de
variación de la demanda diaria.

La matriz resultante concentra la información de gestión en una sola tabla: la celda **AX**
—alta facturación, demanda estable— reúne alrededor del **56% de la facturación** de la cadena,
y es donde la automatización de la reposición rinde más. En el extremo opuesto, la celda **CZ**
representa cerca del **28% del catálogo** por apenas el **3,5% de la facturación**: series donde
una regla simple es preferible a un modelo, y donde la pregunta pertinente no es cuánto reponer
sino si mantener la referencia.

> **[FIGURA 7.9]** *Matriz ABC/XYZ: recuento de series y peso en la facturación.*
> `Fuente: Cuaderno 02. Dos mapas de calor 3x3 con los valores impresos.`

### 7.2.7. Una hipótesis que no sobrevivió: la afinidad entre productos

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
proporción de pares con correlación superior a 0,30 pasa del **5,17% al 2,55%**. Buena parte de
la asociación aparente era, en efecto, calendario.

**La prueba que decide.** Un producto de una tienda y otro de una tienda distinta no pueden
compartir cesta por construcción, de modo que la distribución de sus correlaciones residuales es
el nivel de ruido. Sobre 14.280 pares entre establecimientos distintos, el percentil 99 se sitúa
en **+0,3875**: pares que físicamente no pueden estar relacionados alcanzan correlaciones de
casi 0,4. De los pares del mismo establecimiento, solo el **1,27%** supera ese umbral, frente al
1,00% esperable por azar.

**No hay señal.** El exceso es indistinguible del ruido. Las parejas mejor clasificadas lo
parecen, pero al desplazar una de las dos series un solo día la correlación apenas cae —nitidez
mediana de 0,063—, lo que indica tendencia compartida y no compra simultánea.

La conclusión práctica para DSMarket es concreta: el dato que permitiría responder esta pregunta
es el **identificador de ticket** en el registro de ventas, y hoy no existe. Es la tercera
recomendación de incorporación de datos de este trabajo, después de la merma y el inventario.

### 7.2.8. Qué abre el capítulo siguiente

Con productos y tiendas agrupados, y con la clasificación operativa construida, el trabajo
dispone de la estructura necesaria para modelar. Los grupos entran como variables categóricas en
los modelos de predicción, y la clasificación ABC/XYZ determinará más adelante qué método de
reposición se aplica a cada serie.

La pregunta siguiente es la que el encargo formula de forma más directa: cuánto se va a vender.
