# 3. Introducción

DSMarket es una cadena de distribución minorista con diez establecimientos repartidos entre
Nueva York, Boston y Filadelfia, y un catálogo de 3.049 referencias organizado en tres
categorías comerciales. Como muchas cadenas de su tamaño, la compañía dispone desde hace años
de un registro exhaustivo de sus operaciones —cinco años y cuatro meses de ventas diarias por
producto y tienda, junto con el histórico semanal de precios y el calendario de eventos— y de
muy poca capacidad para convertir ese registro en decisiones. Los datos existen; el uso, no.

El encargo que origina este trabajo procede de la dirección de datos de la compañía y se
formula en cuatro peticiones sucesivas: entender en profundidad cómo se está vendiendo,
agrupar productos y tiendas que se comporten de forma parecida para poder diseñar campañas,
predecir la demanda de las próximas cuatro semanas y, a partir de esa predicción, determinar
qué cantidad de cada producto debe reponerse en cada tienda. A ello se añade una pregunta
concreta del director financiero —si las previsiones de los niveles agregados pueden obtenerse
sumando las previsiones individuales— y una pregunta abierta del área comercial sobre la
posibilidad de explotar las diferencias de precio entre establecimientos.

## 3.1. El problema, formulado con precisión

Las cuatro peticiones anteriores describen un encargo, no un problema de investigación. Traducidas
al lenguaje del análisis, plantean una cadena de preguntas en la que cada una solo tiene sentido
después de haber respondido la anterior:

1. ¿Qué estructura tiene la demanda de DSMarket, y hasta qué punto es homogénea entre tiendas,
   ciudades y categorías?
2. Si no lo es, ¿qué agrupaciones de productos y de tiendas capturan esa heterogeneidad de forma
   estable y reproducible?
3. ¿Con qué precisión puede predecirse la demanda diaria a cuatro semanas vista, y esa precisión
   se mantiene al agregar por tienda, ciudad o categoría?
4. ¿Qué decisión de reposición se deriva de esa predicción, y cuánto vale esa decisión medida en
   dinero y no en error de predicción?
5. ¿Permiten estos datos estimar el efecto causal del precio sobre la demanda?

Este trabajo responde las cinco. La quinta, con una negativa argumentada.

## 3.2. Alcance

El trabajo abarca el ciclo completo desde el fichero en bruto hasta la decisión operativa. Se
construye un almacén analítico sobre los tres ficheros de origen, se caracteriza la demanda, se
segmentan productos y tiendas, se comparan familias de modelos de predicción bajo un mismo
protocolo de validación, se simula una política de reposición sobre las 30.490 series
producto-tienda con la demanda que realmente ocurrió, y se somete a prueba la posibilidad de
estimar la elasticidad precio de la demanda.

Quedan fuera del alcance tres cosas que conviene declarar desde el principio. La primera, el
surtido: el trabajo decide cuánto pedir de lo que ya está en el catálogo, no qué productos
debería tener cada tienda. La segunda, las restricciones logísticas —lotes de proveedor,
capacidad de almacén, unidades de transporte—, de las que no se dispone de información. La
tercera, el efecto de sustitución entre productos: cada serie se trata de forma independiente,
lo que es una simplificación conocida y no una omisión involuntaria.

## 3.3. Qué encontrará el lector

La memoria se organiza como una investigación encadenada y no como un informe de tareas. Tras
la justificación y el estado del arte (§4) y los objetivos (§5), la sección de metodología (§6)
reúne una sola vez el aparato común a todos los capítulos: el origen y la calidad de los datos,
la arquitectura del almacén analítico, el esquema de validación temporal y las métricas de
error. La sección de resultados (§7) desarrolla los seis capítulos de la narrativa, cada uno
abierto por la pregunta de negocio que lo motiva y cerrado por la que abre el siguiente.

El lector encontrará también tres momentos en los que una conclusión propia del trabajo fue
sometida a una prueba que podía refutarla y la prueba la refutó. Están señalados de forma
explícita en cada capítulo y recogidos en las conclusiones, porque son, a juicio de los autores,
el resultado más valioso del proyecto: un hallazgo del análisis exploratorio que se descartó por
falta de sustento, una conclusión sobre el valor del modelo de predicción que la simulación de
la política invirtió, y una elasticidad estadísticamente significativa que una prueba de
falsación dejó sin interpretación causal.
