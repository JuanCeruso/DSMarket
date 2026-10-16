# -*- coding: utf-8 -*-
# Textos de interpretación del notebook 02 (se insertan en los marcadores <<<...>>> de build_notebook_02.py).
# Las cifras salen de la ejecución del notebook; si se cambia el código, hay que revisarlas.

NARRATIVA['<<<DECISION_VARIABLES>>>'] = """
**Decisión: se quitan `cv_daily` y `trend`, y se agrupa con 6 variables.**

- **`cv_daily` y `zero_frac` tienen una correlación de 0,89**: miden casi lo mismo. Un producto que muchos días no vende nada es, por fuerza, un producto que vende a saltos. Se mantiene `zero_frac` porque se explica mejor a negocio ("% de días sin venta").
- **`trend` se deja fuera por otro motivo.** Medida desde el lanzamiento de cada producto ya no repite ninguna otra variable (su correlación más alta es 0,17). Pero describe el ciclo de vida del producto (si está creciendo o decayendo), no *cuándo y cómo* se compra, que es lo que necesita marketing para diseñar campañas. La tendencia ya la recoge el modelo de predicción de la Tarea 3 con sus medias móviles.

**Por qué importa medir desde el lanzamiento:** el 17,8 % de los días-producto son anteriores a la primera venta de cada producto. En una primera versión se contaban como "días sin venta", y eso hacía que `trend` y `zero_frac` tuvieran una correlación de 0,81: los dos estaban midiendo sobre todo *cuándo llegó el producto al catálogo*, no cómo se vende.

Con `cv_daily` dentro, la idea de "vende a saltos" contaría dos veces en la distancia. El resto de pares tiene correlaciones bajas, así que cada variable aporta algo propio.
"""

NARRATIVA['<<<DECISION_ESCALADO>>>'] = """
**Decisión: `StandardScaler`.**

`RobustScaler` hace lo contrario de lo que se busca aquí. Al escalar con la mediana y los cuantiles, los valores extremos quedan todavía más lejos del resto, y **a partir de K=8 K-Means los aísla en grupos de un solo producto**. Con `StandardScaler`, todos los grupos tienen un tamaño razonable en la zona donde se va a elegir K (entre 5 y 8 grupos, el más pequeño tiene al menos 74 productos). Un grupo de un solo producto no sirve para diseñar una campaña.
"""

NARRATIVA['<<<DECISION_K>>>'] = """
**Decisión: K = 6.**

- **Codo:** la curva de la inercia es suave, sin un quiebre brusco (es lo habitual con datos de comportamiento, donde los productos no forman islas separadas sino un continuo). Medido de forma objetiva, la zona del codo (los puntos que más se alejan de la recta) va de **6 a 8 grupos**.
- **Silueta:** dentro de esa zona, K = 6 tiene la mejor silueta (0,167).
- **Tamaño:** el grupo más pequeño tiene 120 productos, suficiente para una campaña propia.

La silueta es más alta con 2, 3 o 4 grupos, pero esas particiones solo separan "productos que venden mucho" de "productos que venden poco": no distinguen el fin de semana, Navidad o los eventos, que es justo lo que necesita marketing. La silueta moderada (0,17) se explica por lo mismo: los productos se reparten de forma continua y los grupos tienen bordes difusos. Lo que se busca es una partición útil y estable, y eso se comprueba en el siguiente apartado.
"""

NARRATIVA['<<<LECTURA_GRUPOS>>>'] = """
**Los 6 grupos.** El nombre de cada grupo dice qué tipo de producto contiene. Cuando una categoría es mayoritaria, aparece en el nombre; cuando el grupo es mixto, se nombra por el momento de compra.

| Grupo | Qué productos contiene | Qué lo define |
|---|---|---|
| **0 · Alimentación de consumo diario** | 72 % alimentación, los más baratos (2,6 $) | Venden mucho (37 unidades al día entre las 10 tiendas) y casi todos los días (5 % de días sin venta). Son el **42 % de la facturación**. |
| **1 · Hogar de fin de semana** | 45 % hogar y jardín | Venden un 42 % más el fin de semana, el valor más alto de todos, y también suben en los eventos. Segundo grupo en facturación (25 %). |
| **2 · Básicos de rotación lenta** | mixto (52 % alimentación, 26 % hogar, 21 % accesorios) | Venden poco (6 unidades al día) y sin picos: son los que menos reaccionan al fin de semana, a diciembre y a los eventos. Son el 24 % del catálogo y el 15 % de la facturación. |
| **3 · Accesorios y hogar de precio alto** | 48 % accesorios + 43 % hogar | Los más caros (17,4 $ de media, más del triple que el resto). Pocas unidades, pero el 11 % de la facturación. |
| **4 · Compra ocasional en fechas señaladas** | mixto (49 % hogar, 28 % alimentación, 23 % accesorios) | El 39 % de los días en que están a la venta no venden nada, pero en SuperBowl, Easter y Labor Day venden un **26 % más** que un día normal. Son el 13 % del catálogo y solo el 4 % de la facturación. |
| **5 · Temporada de Navidad** | mixto (38 % accesorios, 35 % alimentación, 28 % hogar): mesa y regalo | En diciembre venden **casi el doble** (1,89 veces) que el resto del año. |

**Para Joelle:**
- Cada grupo pide una campaña distinta: el grupo 1 se trabaja los viernes y sábados, el grupo 4 en las fechas señaladas del calendario y el grupo 5 en diciembre.
- Para medir si una campaña ha funcionado, conviene comparar cada producto con su grupo y no con el total de la tienda: cada grupo trae ya su propio nivel "normal" de ventas y de estacionalidad.
- El grupo 4 es el candidato a revisar el surtido: ocupa el 13 % del catálogo y aporta el 4 % de la facturación.
"""

NARRATIVA['<<<RESPUESTA_JOELLE>>>'] = """
**Respuesta a Joelle: 6 grupos.**

- **5 grupos** está cerca, pero junta el grupo de Navidad con otros productos y su señal se pierde.
- **10 grupos** afina algo más (separa un núcleo de eventos todavía más extremo), pero empeora la silueta (0,145) y parte los grupos grandes de alimentación y hogar en subgrupos que solo se diferencian en matices. Para planificar campañas, 6 grupos es más manejable.
- **20 grupos** deja un grupo con **un solo producto**: ya no es una segmentación, es una lista.

Además, una sola segmentación evita el problema de tener dos clasificaciones distintas del mismo producto (una con 5 grupos y otra con 10) que no encajan entre sí.
"""

NARRATIVA['<<<CASO_069>>>'] = """
`SUPERMARKET_3_069` vende una mediana de 8 unidades al día entre las 10 tiendas, pero sus cuatro mejores días en cinco años son **cuatro 31 de diciembre**. Es, con toda probabilidad, un producto de Nochevieja.

Sirve para explicar el grupo de Navidad y deja dos avisos para las tareas siguientes:
- **Predicción (Tarea 3):** un modelo que no tenga en cuenta el calendario lo subestimará en diciembre.
- **Reposición (Tarea 4):** el stock de seguridad de estos productos no se puede calcular con la demanda media del año; necesitan una regla de temporada o se agotarán justo el 31.
"""

NARRATIVA['<<<LECTURA_TIENDAS>>>'] = """
**Qué se ve al comparar las tiendas directamente:**

- **Tribeca (Nueva York) se parece más a las tiendas de Boston que a las de su propia ciudad.** Su tienda más parecida es Back Bay y la segunda, South End, ambas de Boston. Comparte con ellas el precio por debajo de la media (−0,39 %, frente a −0,55 % / −0,85 % en Boston y +0,36 % / +0,40 % en el resto de Nueva York), la baja variabilidad diaria y un fin de semana moderado.
- **Las tres tiendas de Boston se parecen mucho entre sí** (son las distancias más pequeñas de la tabla). Boston es la ciudad más homogénea, igual que se vio en el EDA con los productos más vendidos.
- **Harlem y Midtown Village no se parecen a ninguna otra tienda.** Harlem tiene el fin de semana más fuerte (+50 %) y el mayor peso de hogar (28 %). Midtown Village es la única tienda que vende más en diciembre que el resto del año y, junto con Yorktown, la de ventas más irregulares.
- **El precio separa por ciudad:** Boston y Tribeca son las tiendas baratas, Filadelfia la más cara. Las diferencias son menores del 1 %.

**Conclusión para Michelle:** el perfil de una tienda depende más de su barrio y de su clientela que de su ciudad. Si se abre una tienda nueva, la referencia para su surtido y su previsión inicial debería ser la tienda existente más parecida en tipo de barrio, no la media de su ciudad.
"""

NARRATIVA['<<<CONCLUSIONES>>>'] = """
## 6. Conclusiones y uso en las siguientes tareas

| Pedido | Respuesta |
|---|---|
| ¿Cuántos grupos de productos? ¿5, 10 o 20? | **6**, elegidos con el método del codo y la silueta, y estables (ARI 0,98 entre 10 semillas). |
| ¿Qué es cada grupo? | Una ficha con nombre de negocio ligado a los productos que contiene (sección 4.6). |
| ¿Tiene sentido agrupar tiendas? | **No con un algoritmo**: 10 tiendas y más variables que tiendas. Se comparan directamente (sección 5) y aparecen los mismos hallazgos: Tribeca se comporta como Boston, y Harlem y Midtown son atípicas. |

**Decisiones de método, resumidas:**
- Todas las variables se miden **desde la primera venta** de cada producto, para no confundir un lanzamiento tardío con un producto de venta ocasional.
- 6 variables de comportamiento; se quitan `cv_daily` (repite `zero_frac`) y `trend` (describe el ciclo de vida, no el momento de compra).
- `StandardScaler`, porque `RobustScaler` aísla productos sueltos en grupos de uno.
- K-Means con K elegido por el codo (K de 2 a 14) y la silueta.

**Qué pasa a las tareas siguientes:**
- **Tarea 3 (predicción):** el grupo de producto entra como variable del modelo. Ya no se usa ningún grupo de tiendas; la tienda y la ciudad ya están en el modelo como variables propias.
- **Tarea 4 (reposición):** los grupos ayudan a describir cada producto, pero la política de reposición se decide **simulando su coste** (Tarea 4), no por el grupo ni por el error de predicción: la Tarea 4 muestra que el modelo ahorra más justo en los productos de venta irregular. El grupo 5 sí necesita una regla de temporada.

**Limitación:** la silueta es moderada (0,17) porque los productos forman un continuo y no grupos separados. Los grupos son una forma útil y estable de ordenar el catálogo, no "tipos naturales" de producto.
"""
