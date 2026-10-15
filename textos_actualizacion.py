# -*- coding: utf-8 -*-
# Textos de interpretación de las secciones de actualización de los notebooks 03 y 04.

textos['HALLAZGO_03'] = """
**Hallazgo: el cambio de segmentación no altera los resultados del modelo.**

| | Segmentación anterior | Segmentación actual |
|---|---|---|
| WRMSSE medio (3 tramos) | 1,0414 | **1,0406** |
| Peso de las variables de segmentación en el modelo | 0,06 % | 0,03 % |

- **La versión anterior reproduce exactamente el resultado de la sección 6** (WRMSSE 1,0414), lo que confirma que el reentrenamiento es comparable.
- Con la segmentación actual el error es **prácticamente el mismo** (un 0,08 % menor), con una variable en lugar de tres.
- Las variables de segmentación pesan menos del 0,1 % de la importancia del modelo, frente a cerca de dos tercios de la media móvil de 28 días. Es coherente con la sección 6: el modelo es, en el fondo, una media móvil corregida, y la identidad del producto y la tienda ya entran por sus propias variables.

**Consecuencia:** las conclusiones de las secciones 6 a 14 siguen siendo válidas con la segmentación actual. Lo que cambia es la lectura por grupo de producto, que se rehace a continuación.

Una nota sobre las secciones 7 y 12: incluyen un nivel de agregación por "grupo de comportamiento" de tiendas, construido con la segmentación anterior. Ese nivel ya no existe. En la sección 7 se vio que no mejoraba la predicción respecto a agregar por ciudad, así que se mantiene la ciudad como eje de reporte.
"""

textos['HALLAZGO_03_GRUPOS'] = """
**Hallazgo: el modelo funciona donde está el volumen y no aporta en la compra ocasional.**

- **Alimentación de consumo diario y Hogar de fin de semana** suman el **80 % de las unidades** y tienen el mejor error (RMSSE 0,79). Ahí el modelo funciona y supera ligeramente a la media móvil.
- **Compra ocasional en fechas señaladas** tiene un RMSSE de **1,19**, y la media móvil tampoco lo hace mejor (1,19). Son productos que no venden nada más de la mitad de los días: producto a producto, esa demanda no se puede predecir. Es el equivalente a la "cola larga" de la sección 10.
- **Básicos de rotación lenta** y **Temporada de Navidad** quedan cerca de 1: el modelo apenas aporta sobre una regla simple. En el caso de Navidad, los tramos de validación son de febrero a abril, así que no recogen su temporada.

**Para la Tarea 4:** la reposición basada en predicción tiene sentido en los dos grupos grandes. En la compra ocasional y los básicos de rotación lenta corresponde una política de punto de pedido, y en Navidad una regla de temporada.
"""

textos['HALLAZGO_04'] = """
**Hallazgo: los dos ejes siguen siendo complementarios con los grupos actuales.**

- **Alimentación de consumo diario** es el grupo con más series estables (X: 38,5 %), pero aun así un 15 % de sus series son erráticas (Z).
- En **Básicos de rotación lenta**, **Compra ocasional en fechas señaladas**, **Accesorios y hogar de precio alto** y **Temporada de Navidad**, cerca de la mitad de las series son Z (entre el 50 % y el 56 %).

El grupo dice *cómo* se vende un producto (a diario, en fin de semana, en Navidad, en fechas señaladas) y la clase XYZ dice *cuánto se puede fiar* la previsión. Para decidir la política de reposición hacen falta los dos, igual que concluía la sección 3 con la segmentación anterior.

*Nota:* el cruce usa todas las series y los 90 días anteriores a la ventana simulada, con la misma regla XYZ de la sección 3.
"""

# ======================================================================
# Sección 16: revisión tras la tutoría
# ======================================================================
textos['MD_16_INTRO'] = """
## 16. Revisión tras la tutoría

En la tutoría salieron cuatro puntos sobre esta tarea:

1. **Nivel y horizonte:** la predicción debe hacerse a semana vista y al máximo desglose, producto a producto.
2. **Un ejemplo concreto:** un gráfico de una serie con lo que teníamos, lo que tendría que haber pasado y lo que predice el modelo.
3. **Otra forma de medir el error:** hay muchos días sin ventas, y eso hace que medir día a día sea engañoso.
4. **Eventos a nivel semanal:** festivos y días especiales como Navidad o Black Friday mueven las compras de toda la semana, no solo del día.

Esta sección responde a cada uno. Todo parte del modelo actualizado de la sección 15 (LightGBM por bloques semanales con los 6 grupos de producto actuales). El código nuevo está en `forecast_semanal.py`.
"""

textos['MD_16_1'] = """
### 16.1. Nivel y horizonte: ya se cumple

- **Semana vista.** El modelo predice las 4 semanas siguientes al día del corte, y lo hace por bloques semanales: un modelo para la semana 1, otro para la 2, otro para la 3 y otro para la 4 (sección 6). Cada uno usa la información más reciente que tendría disponible en la realidad.
- **Máximo desglose.** Se predice cada producto en cada tienda: 30.490 series, el nivel más fino que permiten los datos. Los totales por tienda, ciudad o categoría se obtienen sumando, y la sección 7 comprobó que sumar es válido.

No hace falta cambiar nada en este punto.
"""

textos['MD_16_2'] = """
### 16.2. Un ejemplo concreto

Dos series reales de la última ventana de validación (28 de marzo a 24 de abril de 2016):

- un producto de **alimentación de consumo diario** que se vende casi todos los días;
- un producto de **compra ocasional** que no se vende la mitad de los días.

A la izquierda, día a día: en gris lo que teníamos antes de predecir, en azul oscuro lo que pasó de verdad y en naranja lo que predijo el modelo. A la derecha, las mismas 4 semanas sumadas.
"""

textos['MD_16_3'] = """
### 16.3. Medir el error por semanas

Hasta ahora el error se medía **día a día** (RMSSE y WRMSSE, sección 3.1). Con tantos días sin ventas eso tiene dos problemas:

- En un producto que vende 0 o 1 unidades al día, el modelo predice, por ejemplo, 0,4. Cada día "falla" aunque en la semana acierte el total.
- La referencia del RMSSE (predecir cada día con el dato del día anterior) es difícil de explicar a negocio.

Proponemos medir también el **WAPE semanal**: se suman las unidades predichas y las vendidas de cada producto y tienda en cada semana, y se calcula qué parte de lo vendido fue error:

$$\\text{WAPE} = \\frac{\\sum |\\text{predicho} - \\text{real}|}{\\sum \\text{real}} \\times 100$$

Se lee directamente: *"el modelo se equivoca en un X % de las unidades de la semana"*. No falla con los ceros, porque divide entre el total vendido y no entre cada día, y encaja con la reposición, que también es semanal.
"""

textos['MD_16_4'] = """
### 16.4. Eventos a nivel semanal

Hasta ahora el modelo solo sabía si **ese día** había un evento. Pero las compras de Navidad, Thanksgiving o la Super Bowl se reparten por los días anteriores. Se añaden cuatro variables que miran la semana:

| Variable | Qué dice |
|---|---|
| `sem_evento` | si en esa semana (sábado a viernes, como el calendario original) hay algún evento |
| `evento_semana` | qué evento hay esa semana |
| `dias_hasta_evento` | cuántos días faltan para el próximo evento (hasta 15) |
| `dias_desde_evento` | cuántos días han pasado desde el último (hasta 8) |

Todas se conocen de antemano por el calendario, así que no usan información del futuro. Se reentrena el modelo con ellas y se compara con el de la sección 15 en las 3 ventanas de validación y en las 2 de temporada alta de la sección 8 (noviembre y diciembre de 2015), que es donde los eventos pesan de verdad.
"""

textos['HALLAZGO_16_2'] = """
**Hallazgo: día a día el error parece enorme; por semanas, el modelo acierta bastante bien.**

- **Producto de venta diaria** (alimentación, Filadelfia): vende unas 7-8 unidades al día. Día a día el modelo se equivoca en torno a un 40 % de las unidades, porque no puede saber si mañana se venderán 5 o 10. Pero **por semanas el error baja a un 7 %**: vendió 51, 53, 57 y 41 unidades, y el modelo predijo 51, 56, 50 y 46.
- **Producto de compra ocasional** (Nueva York): no se vende más de la mitad de los días. Día a día el error supera el 100 %: es imposible adivinar qué día concreto aparecerá un comprador. **Por semanas baja a un 25 %**: en las 4 semanas se vendieron 40 unidades y el modelo predijo 33.

Para reponer una tienda no hace falta saber qué día exacto se venderá cada unidad, sino cuántas hacen falta en la semana. Por eso el error que importa es el semanal (16.3).
"""

textos['HALLAZGO_16_3'] = """
**Hallazgo: medido por semanas, el error se reduce a la mitad y los ceros casi desaparecen.**

| | Día a día | Por semanas |
|---|---|---|
| Huecos sin ventas | 57 % de los días | 19 % de las semanas |
| Error del modelo (WAPE) | 75,6 % | **40,2 %** |
| Error de la media móvil de 28 días (WAPE) | 75,3 % | 39,6 % |

*(media de las 3 ventanas de validación)*

- **La nota de la tutora se confirma.** Más de la mitad de los días no se vende nada, así que medir día a día mezcla el error del modelo con el azar de qué día cae cada venta. Por semanas, los ceros bajan al 19 % y el error al 40 %.
- **Lectura honesta:** con el WAPE semanal, el modelo y la media móvil de 28 días quedan **prácticamente empatados**. La ventaja del modelo en el WRMSSE (un 2,3 %, sección 6) viene de dos cosas que el WAPE no premia: acierta mejor el reparto entre días de la semana (que desaparece al sumar la semana) y pesa más en los productos que más facturan.
- **Consecuencia para el negocio:** para reponer todo el catálogo semana a semana, una media móvil bien hecha ya da casi el mismo resultado. El modelo aporta donde hay más dinero en juego y en los días con picos.

Proponemos usar las dos métricas: el **WRMSSE** para comparar modelos, porque es la métrica de referencia en este tipo de problema, y el **WAPE semanal** para explicar el error a negocio y para la reposición.
"""

textos['HALLAZGO_16_3_GRUPOS'] = """
**Hallazgo: el error semanal depende sobre todo de lo regular que sea el producto.**

- **Alimentación de consumo diario** tiene el menor error (36 %) y **Hogar de fin de semana** le sigue (41 %). Son los dos grupos con menos semanas sin ventas (10-14 %). Hogar de fin de semana es el único grupo grande donde el modelo supera a la media móvil.
- **Básicos de rotación lenta** y **Compra ocasional en fechas señaladas** rondan el 50 %: una de cada cuatro semanas no venden nada.
- **Temporada de Navidad** es el peor (69 %), pero estas ventanas son de febrero a abril, fuera de su temporada.

Coincide con lo visto en la sección 15.1: el modelo funciona donde está el volumen.
"""

textos['HALLAZGO_16_4'] = """
**Hallazgo: tratar los eventos a nivel semanal no mejora el modelo con los datos que tiene para aprender.**

| Ventana | Modelo sección 15 | Con eventos semanales |
|---|---|---|
| Feb 2016 | 1,0752 | 1,0758 |
| Mar 2016 | 1,0422 | 1,0411 |
| Abr 2016 | 1,0044 | 1,0030 |
| Nov 2015 (Thanksgiving) | 1,0525 | 1,0539 |
| Dic 2015 (Navidad) | 1,1090 | 1,1118 |

*(WRMSSE, menor es mejor; el WAPE semanal tampoco cambia más de 0,3 puntos)*

Las cuatro variables nuevas juntas pesan un **0,17 %** de la importancia del modelo, frente a cerca de dos tercios de la media móvil de 28 días. ¿Por qué no aportan, si la idea es buena?

1. **El modelo aprende de los últimos 180 días** (sección 6). Para predecir diciembre aprende de junio a noviembre: **no ha visto ninguna Navidad**, así que no puede saber qué pasa la semana antes de una. Es el mismo problema que ya señalaba la sección 8.
2. **El calendario tiene pocos eventos**: solo 5 tipos (Super Bowl, Ramadán, Thanksgiving, Año Nuevo y Semana Santa), más Navidad y Labor Day añadidos por fecha. En cada ventana de entrenamiento entran 2 o 3, cada uno con su propio efecto.
3. **El modelo ya mira el año anterior**: la variable `lag_364` le dice cuánto se vendió el mismo día del año pasado, que recoge buena parte del efecto de cada temporada.

La idea de la tutora es correcta, pero para que funcione el modelo tiene que aprender con **más de un año de historia**, de forma que vea al menos un ejemplo de cada evento. Se prueba en el apartado 16.5.
"""

textos['HALLAZGO_16_4_DIC'] = """
**Hallazgo: por semanas se ve claro dónde falla diciembre, y las variables semanales no lo corrigen.**

- Las tres primeras semanas el modelo **se queda corto**, y cada vez más a medida que se acerca Navidad: un 3 %, un 6 % y un 9 % por debajo de lo vendido.
- La semana del 25 al 31 **se pasa en un 14 %**, porque predice unas 36.000 unidades el día 25, cuando la tienda cierra.
- Las dos versiones del modelo hacen prácticamente lo mismo.

Para corregirlo, el modelo tiene que haber visto al menos un diciembre anterior. Es lo que se prueba a continuación.
"""

textos['MD_16_5'] = """
### 16.5. Más historia: 400 días en lugar de 180

Se repite la comparación entrenando con los **400 días** anteriores a cada ventana en lugar de 180. Así, para predecir diciembre de 2015 el modelo ya ha visto la Navidad, el Thanksgiving y el Año Nuevo de 2014. Se prueban las dos versiones, sin y con eventos semanales, para separar el efecto de tener más historia del efecto de las variables nuevas.
"""

textos['HALLAZGO_16_5'] = """
**Hallazgo: con más historia el modelo mejora mucho en temporada alta, y no empeora el resto del año.**

| Ventana | 180 días | 400 días | 400 días + eventos semanales |
|---|---|---|---|
| Nov 2015 (Thanksgiving) | 1,0525 | 1,0203 | **1,0167** |
| Dic 2015 (Navidad) | 1,1090 | 1,0519 | **1,0459** |
| Media feb-abr 2016 | 1,0406 | 1,0378 | **1,0376** |

*(WRMSSE, menor es mejor)*

- **Diciembre mejora un 5,7 %** y noviembre un 3,4 %: es la mayor mejora de todo el proyecto, justo en los meses que más importan.
- **El grueso de la mejora viene de tener más historia** (400 días). Las variables de evento semanal añaden un poco más en temporada alta (un 0,6 % en diciembre y un 0,4 % en noviembre) y nada el resto del año.
- **En febrero-abril también mejora un poco** (de 1,0406 a 1,0376), así que alargar la historia no tiene coste en precisión. Solo lo tiene en tiempo de cálculo: cada entrenamiento tarda algo más del doble.
- Con el **WAPE semanal** pasa lo mismo: diciembre baja del 47,2 % al 41,4 %, y en febrero-abril el modelo pasa del 40,2 % al 39,6 %, a la altura de la media móvil de 28 días.

**La tutora tenía razón en el fondo:** los eventos hay que mirarlos con perspectiva semanal y anual. Pero lo que más pesa no son las variables nuevas, sino que el modelo pueda **ver el evento del año anterior**.
"""

textos['HALLAZGO_16_5_DIC'] = """
**Hallazgo: con 400 días de historia el modelo aprende solo los tres problemas de diciembre que señalaba la sección 8.**

1. **El cierre del 25 de diciembre.** Antes predecía unas 36.000 unidades ese día; ahora predice **96** (la realidad fueron 14). Lo aprende al ver la Navidad de 2014, sin aplicar ninguna regla a mano.
2. **La subida previa a Navidad.** La semana del 18 al 24 pasa de quedarse un 9,4 % por debajo a un **6,3 %**. Los días 22, 23 y 24 son donde más ayudan las variables de evento semanal.
3. **La semana del 25 al 31** pasa de pasarse un 14,5 % a quedarse un 7,8 % por debajo. Sigue sin captar del todo el pico del 31 de diciembre.

En noviembre, la semana de Black Friday (27 de noviembre a 3 de diciembre) pasa de un error del 10 % a **prácticamente cero**.
"""

textos['MD_16_6'] = """
### 16.6. Resumen de la revisión

| Punto de la tutoría | Respuesta |
|---|---|
| Semana vista y máximo desglose | **Ya se cumple**: 4 semanas, modelo por bloques semanales, 30.490 series producto × tienda. |
| Ejemplo concreto | **Añadido** (16.2): por semanas el error baja del 41 % al 7 % en un producto diario y del 104 % al 25 % en uno ocasional. |
| Métrica con días sin ventas | **Añadido el WAPE semanal** (16.3): el error pasa del 76 % día a día al 40 % por semanas. Con esta métrica el modelo de 180 días empata con la media móvil. |
| Eventos a nivel semanal | **Probado** (16.4 y 16.5): con 180 días de historia no aportan; con **400 días** el modelo mejora un 5,7 % en diciembre y un 3,4 % en noviembre, y las variables semanales suman una pequeña mejora en temporada alta. |

**Propuesta para el modelo final:** entrenar con 400 días de historia y con las variables de evento semanal. Mejora en todas las ventanas de temporada alta, no empeora el resto del año, y aprende por sí solo los cierres de Navidad sin reglas manuales.

**Siguientes pasos:**
- Regenerar con esta configuración la predicción final de 28 días (sección 13) y los ficheros de la entrega.
- Reportar el WAPE semanal junto al WRMSSE en la memoria y en la aplicación.
"""
