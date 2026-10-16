## 7.7. Conclusiones

### 7.7.1. Respuesta a los objetivos

**OE1 — Caracterizar la estructura de la demanda.** La demanda de DSMarket no es homogénea en
ninguna de las dimensiones examinadas. Solo cinco de los quince productos más vendidos son
comunes a las tres ciudades, y Filadelfia se aparta del resto con solo cuatro. Tres eventos del
calendario tienen efecto medible —Labor Day, SuperBowl y Easter, entre el 15% y el 22%— y uno
que se esperaba relevante, Black Friday, va en sentido contrario: vende un 24 % menos que un
viernes normal. Medidos por semanas, los eventos mueven también las semanas vecinas: las dos
semanas previas a Navidad venden un 4-5 % más. La categoría con mayor dispersión de
precios entre tiendas es SUPERMARKET, con un 2,75%, en contra de la expectativa inicial.

**OE2 — Segmentar el catálogo y la red.** Seis grupos de producto elegidos con el método del
codo y estables entre semillas (índice de Rand ajustado 0,98), con nombres ligados a lo que
contienen: Alimentación de consumo diario, Hogar de fin de semana, Básicos de rotación lenta,
Accesorios y hogar de precio alto, Compra ocasional en fechas señaladas y Temporada de Navidad.
Las variables se miden desde la primera venta de cada producto, para no confundir un lanzamiento
tardío con un producto de venta ocasional. Los dos primeros grupos reúnen el 68 % de la
facturación; el de Navidad vende casi el doble en diciembre y el de fechas señaladas un 26 % más
en los días de evento. Las tiendas no se agruparon con un
algoritmo —diez tiendas con más variables que observaciones— sino que se compararon
directamente, y la comparación muestra que **el perfil de demanda de una tienda no respeta las
fronteras de ciudad**: Tribeca se parece más a Boston que a Nueva York. Ese parecido tiene además
un uso operativo (§7.3.10).

Se evaluó además la posibilidad de derivar recomendaciones de venta cruzada y **se descartó con
evidencia**: el co-movimiento aparente entre productos se explica por el calendario y el tráfico
de la tienda, y lo que queda no supera el nivel de ruido medido entre establecimientos distintos
(1,27% frente al 1,00% esperable por azar).

**OE3 — Predecir la demanda.** El mejor resultado corresponde a LightGBM con objetivo Tweedie y
estrategia por bloques semanales, con un WRMSSE de 1,0414. El hallazgo metodológico es que **la
estrategia de horizonte pesó unas veinte veces más que la elección de biblioteca**: con la
formulación ingenua ningún modelo supera a una media móvil. Una búsqueda de hiperparámetros
posterior confirmó que el margen restante no estaba en la configuración del modelo —mejora
del −0,02% en WRMSSE—, mientras que **reformular el objetivo como el total del ciclo redujo el
error un 15,7% y eliminó un sesgo del −7,4%**. Las dos comprobaciones apuntan en la misma
dirección: el rendimiento estaba en el planteamiento, no en el modelo.

La revisión de la tutoría añadió dos cambios al modelo final. Medido **por semanas** (WAPE semanal),
que es como se repone, el error baja del 76% al 40%, porque más de la mitad de los días no hay
ventas. Y entrenar con **400 días de historia** en lugar de 180, con variables de evento a nivel
semanal, mejora el WRMSSE un 5,7% en diciembre y un 3,4% en noviembre sin empeorar el resto del año
(1,0376 de media en febrero-abril), y el modelo aprende por sí solo el cierre del 25 de diciembre.

**OE4 — Los agregados.** Sumar es válido y preferible a modelar cada nivel por separado, pero
reconciliar con MinT es mejor que sumar: mejora el error en los seis niveles de la jerarquía, de
un 15,12% a un 13,71% de error porcentual absoluto medio, y garantiza además la coherencia entre
informes.

**OE5 — La política de reposición.** La política de partida pierde casi quince dólares de margen por
cada dólar de inventario inmovilizado. La política propuesta, híbrida según la clase XYZ, eleva el
nivel de servicio del 86,6% al 96,2% con una reducción del coste total del 62,5%. El nivel de servicio óptimo lo decide
la merma y no el margen, lo que convierte la medición de la merma por categoría en la
recomendación operativa más urgente para la compañía.

La comparación de candidatos por coste simulado añadió un resultado que no se buscaba: **el nivel
de servicio del 0,90 aplicado uniformemente resultó ser 2,45 veces más caro** que el candidato
óptimo, y el ratio crítico correcto para los supuestos centrales es 0,714. El parámetro fijado
por convención, y nunca sometido a comprobación, era la decisión más costosa del sistema.

**OE6 — La elasticidad precio.** No se puede estimar con estos datos. La especificación habitual
da una elasticidad de −0,395 con un estadístico $t$ de −19,3, y una prueba placebo con el precio
de la semana siguiente da −0,398. Se propone el experimento aleatorizado que sí permitiría
responder, con su cálculo de potencia: 451 series por brazo durante ocho semanas.

**OE7 — La sostenibilidad del sistema.** Almacén analítico de tres capas reconstruible en veinte
segundos, con las predicciones realimentadas como tabla de hechos y tres consumidores —servicio
de reposición, panel interactivo y cuadro de mando— leyendo las mismas tablas.

### 7.7.2. El hilo conductor: cuatro veces que la evidencia nos contradijo

Los resultados anteriores son los que el encargo pedía. El resultado del que este trabajo se
siente más responsable es otro, y recorre los seis capítulos: en cuatro ocasiones una conclusión
o una hipótesis atractiva fue sometida a una prueba que podía refutarla, y la prueba la refutó.

**Primera. Un hallazgo que hubo que aprender a no publicar.** Black Friday no mostraba el pico
esperado; medido con cuidado, vende incluso un 24 % menos que un viernes normal. Era tentador
presentarlo como una oportunidad comercial desaprovechada —es un titular atractivo y difícil de
contradecir— pero el dato no lo sostenía. Se descartó como evento de pico del calendario. El criterio que se estableció entonces gobierna el resto del documento: un hallazgo
que resulta conveniente para la narrativa y que el dato no sostiene no entra.

**Segunda. Una métrica de error no es una métrica de negocio.** El capítulo de predicción
medía el menor error en Alimentación de consumo diario y uno de los mayores en Compra ocasional
en fechas señaladas. La simulación de la política demostró lo contrario de lo que eso sugiere: el
modelo aporta un 26% en la compra ocasional y resta un 7% en la alimentación diaria. Elegir la
política por el RMSSE habría producido la decisión equivocada en los dos extremos. La generalización de este hallazgo —que la función de pérdida con la que se
elige el modelo debería ser la del negocio, y que esa función coincide con la pérdida pinball
evaluada en el ratio crítico— es la aportación metodológica que el trabajo considera más
transferible a otros problemas.

**Tercera. Un coeficiente significativo no es una identificación creíble.** Una elasticidad de
−0,40, con un estadístico $t$ de −19 y una descomposición por arquetipo perfectamente razonable,
quedó desmontada por una prueba placebo que cuesta cinco líneas de código. Sin esa prueba, la
memoria habría construido una recomendación de precios sobre una correlación espuria.

**Cuarta, y la más barata de todas. Una correlación no es una cesta.** La segmentación por
comportamiento invitaba a buscar productos que se compraran juntos. Bastó comparar los pares del
mismo establecimiento con pares de establecimientos distintos —que no pueden compartir cesta por
construcción— para ver que el exceso era del 1,27% frente al 1,00% esperable por azar. La prueba
costó dos minutos; sin ella, el trabajo habría publicado como hallazgo unas parejas cuya
correlación residual alcanza 0,39 incluso entre tiendas que nunca comparten un cliente.

Los cuatro casos comparten estructura: una conclusión atractiva, una prueba barata que podía
tumbarla, y la decisión de ejecutar la prueba antes de escribir la conclusión. Es lo que
distingue un análisis de una presentación de resultados.

### 7.7.3. Limitaciones

Se enumeran las que afectan a la validez de las conclusiones, ordenadas por importancia.

1. **La demanda está censurada y no se dispone del inventario real.** Las ventas registradas no
   son la demanda: un cero puede corresponder a ausencia de demanda o a ausencia de producto, y
   estos datos no los distinguen. El sesgo recorre todo el trabajo —el modelo predice por debajo,
   la simulación infravalora el coste de la rotura— y no es corregible sin datos de inventario,
   solo acotable (§7.4.7). Su dirección es conocida y favorable: sobre el período simulado, el
   coste real de la rotura se sitúa entre 186.821 y 338.520 dólares frente a los 164.496
   medidos, de modo que **todas las cifras de coste de rotura presentadas son conservadoras** y
   la asimetría frente al coste de mantenimiento pasa de quince a uno a situarse entre diecisiete
   y treinta a uno. Además, toda la evaluación de la política se apoya en una
   simulación y no en su aplicación: la cifra de ahorro del 62,5% es el resultado de un modelo de
   costes, no una medición.
2. **Los parámetros económicos son supuestos.** Margen, coste de posesión y merma no fueron
   facilitados por la compañía. Las conclusiones sobre el nivel de servicio óptimo son
   condicionales a esos supuestos, y por eso se presentan como una curva y no como un número.
3. **No hay efecto de sustitución.** Cada serie se trata de forma independiente. La rotura de un
   producto probablemente desplaza demanda hacia otro, y ese efecto no está modelado.
4. **La segmentación de productos tiene bordes difusos.** La silueta de la partición elegida es
   moderada (0,17) porque los productos forman un continuo y no grupos separados. Los grupos son
   una forma útil y estable de ordenar el catálogo, no tipos naturales de producto.
5. **La temporada alta sigue siendo el período más difícil.** Entrenar con 400 días, que incluyen
   el año anterior, corrigió el fallo más grave —el cierre del 25 de diciembre— y mejoró
   diciembre un 5,7 %, pero el pico del 31 de diciembre sigue infravalorado y la validación en
   temporada alta se apoya en un solo año.
6. **El calendario de eventos es el proporcionado.** No se dispone de promociones planificadas ni
   de acciones de la competencia, que son determinantes conocidos de la demanda minorista.

### 7.7.4. Trabajo futuro

Ordenado por retorno esperado y no por sofisticación técnica, que es la conclusión práctica más
útil que deja el trabajo.

**Recalibrar el nivel de servicio por segmento con el ratio crítico.** Es la consecuencia
inmediata de §7.4.5 y la de mayor efecto económico medido: sustituir el 0,90 uniforme por el
$\tau^{*}$ que corresponde a la economía de cada producto. Requiere el dato de merma por
categoría, que es también la primera recomendación de este trabajo.

**Adoptar el modelo del total del ciclo.** La reformulación de §7.3.9 está validada y no se ha
incorporado a la política, que sigue sumando predicciones diarias. Integrarla es trabajo de
ingeniería, no de investigación.

**Métodos específicos para demanda intermitente.** La compra ocasional y las series de clase Z
siguen siendo donde el error de predicción es mayor, y la comparación de §7.4.5 lo confirma por otra vía: en el
segmento CZ la media móvil simple supera al modelo.

**Predicción de productos sin histórico.** Una referencia nueva llega al lineal sin retardos ni
medias móviles, es decir sin el 88% de la información que usa el modelo, y es justo el momento en
que un error de dimensionamiento resulta más caro. La vía natural es predecir su nivel de demanda
a partir de sus atributos y del comportamiento de la misma referencia en la tienda más parecida,
lo que da un uso operativo a la comparación de tiendas de §7.2.

**Revisión del surtido.** La celda CZ de la matriz ABC/XYZ concentra cerca del 28% del catálogo
por el 3,5% de la facturación. La política de reposición da el surtido por dado; la pregunta de
qué referencias conviene mantener queda abierta y es respondible con los datos disponibles,
siempre que el criterio incorpore los frenos adecuados —no retirar la última referencia de un
departamento en una tienda, ni la que en esa tienda concreta rota mejor que en el resto de la
red.

**El experimento de precios.** Es la única vía para responder la pregunta del capítulo §7.5, y
su diseño y dimensionamiento ya están calculados.

**Registrar la decisión final del encargado.** Es el dato que falta para medir si el sistema
sirve, y el que convertiría el proyecto en un sistema que aprende.

**Incorporar el inventario diario al registro.** Es el dato que convertiría las cotas de §7.4.7 en
una medición, permitiría entrenar los modelos sobre demanda no censurada y cerraría la limitación
principal del trabajo. Después de medir la merma, es la recomendación de mayor valor para la
compañía.

**Alternativas evaluadas y descartadas.** Se documentan aquí porque distinguen un trabajo que
exploró el espacio de soluciones de uno que se detuvo en la primera opción que funcionó. La
**búsqueda de hiperparámetros** se ejecutó y no mejoró el modelo (−0,02% en WRMSSE): la
configuración estaba en una zona plana. La **predicción conforme** se ejecutó y confirmó que el
intervalo ya estaba bien calibrado, aportando garantía formal pero no rendimiento. El **análisis
de afinidad entre productos** se ejecutó y no encontró señal por encima del ruido. Y quedan
descartadas sin ejecutar, por diagnóstico previo, las **arquitecturas neuronales genéricas**,
superadas por los ensambles de árboles en problemas de esta estructura, y un **modelo de mayor
capacidad**, dado que la media móvil de 28 días concentra el 71,7% de la importancia y el techo
lo pone el ruido de la serie.
