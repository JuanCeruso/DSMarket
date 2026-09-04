# Defensa DSMarket — guion de 20 minutos

Cuatro intervenciones, 18 minutos hablados y 2 de reserva. El reparto sigue quién escribió cada
parte de la memoria: es la única asignación que no obliga a nadie a defender material ajeno.

## Regla de oro

**Nunca se lee una diapositiva.** La diapositiva lleva una cifra y una imagen; el argumento lo
pone la voz. Si una diapositiva se entiende sola, sobra la persona; si la persona se entiende
sola, sobra la diapositiva.

## Orden de intervención

### 0:00 — 4:00 · Persona A · El caso y por qué la reposición es el problema

Abrir con la cifra, no con el contexto:

> «DSMarket pierde ciento sesenta y un mil dólares de margen cada cuatro semanas por productos
> que no están en el estante, y solo once mil por inventario inmovilizado. Catorce a uno. La
> cadena no tiene un problema de exceso de stock: tiene un problema de rotura.»

Y después el encargo: diez tiendas, tres ciudades, 3.049 referencias, cinco años de venta diaria,
58 millones de observaciones. Cuatro peticiones que en realidad son una cadena de preguntas
encadenadas, y la última es la única que mueve dinero: cuántas unidades pedir.

Cerrar entregando la palabra: «Antes de predecir nada había que saber si la cadena es una sola
cosa o son diez cosas distintas.»

- 3 diapositivas: la cifra · el encargo · la cadena de preguntas.

### 4:00 — 8:00 · Persona C · Qué está pasando en las tiendas

Dos hallazgos, uno detrás de otro, sin relleno entre medias.

**Uno.** De los quince productos más vendidos en cada ciudad, solo cinco son comunes a las tres.
Filadelfia baja a cuatro de quince. Una promoción uniforme para toda la red desperdicia esfuerzo
en dos tercios del catálogo.

**Dos.** Al agrupar las tiendas por su perfil de demanda salen tres grupos, y **no coinciden con
las ciudades**: Tribeca se comporta como una tienda de Boston. Aquí es donde hay que anticiparse
a la objeción antes de que la hagan:

> «Con solo diez tiendas, un resultado así puede ser inestabilidad del algoritmo. Repetimos la
> segmentación diez veces quitando una tienda cada vez: el grupo se mantuvo unido en las diez,
> con similitud de Jaccard igual a uno.»

Cerrar con la matriz ABC/XYZ en diez segundos —AX es el 56% de la facturación, CZ es el 28% del
catálogo por el 3,5%— porque es lo que usa el capítulo siguiente.

- 4 diapositivas: solapamiento por ciudad · los tres grupos de tienda · la validación por
  exclusión · la matriz ABC/XYZ.

### 8:00 — 14:00 · Persona D · Predecir, y decidir

El bloque más largo y el que decide la nota. Tiene tres momentos.

**Momento 1 — el resultado incómodo, contado primero.**

> «Con el planteamiento inicial ninguno de nuestros modelos le ganaba a una media móvil de
> veintiocho días. No era que estuvieran mal ajustados: el problema estaba mal planteado. Para
> predecir a veintiocho días no se puede usar el dato de ayer, porque cuando predices todavía no
> existe.»

Y entonces la solución: cuatro modelos, uno por semana del horizonte, cada uno con el retardo
mínimo que le corresponde. WRMSSE 1,0414. **La frase que hay que decir:** la estrategia de
horizonte pesó unas veinte veces más que la elección de biblioteca.

**Momento 2 — la respuesta al director financiero.** Sumar es válido. Reconciliar con MinT es
mejor: mejora en los seis niveles, del 15,12% al 13,71%. Y añade algo que importa más que el
punto de error — la coherencia garantizada: el informe de dirección no puede contradecir al de
operaciones.

**Momento 3 — la refutación.** Es el minuto más valioso de toda la defensa. Decirlo despacio:

> «En el capítulo de predicción concluimos, mirando el error, que el modelo servía en las series
> estables y no en la cola larga. Al simular la política de reposición sobre las treinta mil
> series con la demanda real, salió lo contrario: aporta un diecinueve por ciento en la cola
> larga y resta un ocho por ciento en el núcleo estable. Habíamos elegido con una métrica
> simétrica un problema que no lo es. Quedarse corto cuesta el margen; pasarse cuesta el
> almacenaje. No es lo mismo.»

Y el remate teórico, que es lo que separa esta defensa de una presentación de resultados: el
coste del *newsvendor* es la pérdida pinball evaluada en el ratio crítico. La métrica de negocio
tiene forma estadística exacta.

Cerrar con la curva de servicio y el hallazgo de dirección: **el nivel óptimo lo decide la merma,
no el margen** — y por eso la recomendación no es un número, es medir la merma por categoría.

Treinta segundos para el precio: elasticidad de −0,395 con t de −19, placebo con el precio de la
semana siguiente −0,398, efecto desaparecido. «Con estos datos no se puede responder; con
cuatrocientas cincuenta y una series por brazo durante ocho semanas, sí.»

- 6 diapositivas: la estrategia de horizonte · comparación de modelos · MinT por nivel · el
  cambio de signo por segmento · la curva de servicio · el placebo.

### 14:00 — 18:00 · Persona B · Cómo se sostiene, y el cierre

Empezar por el problema, no por la solución: cuatro cuadernos leyendo ficheros sueltos son cuatro
verdades distintas en seis meses.

Enseñar el sistema en un diagrama: bronce, plata, oro; las predicciones vuelven al almacén como
una tabla de hechos; tres consumidores —API, panel y Power BI— leyendo las mismas tablas. La
frase: 490 megas de CSV a 22 en bronce, 58 millones de filas en cuatro segundos, reconstrucción
completa en veinte.

**Demo en vivo, 60-90 segundos.** Una sola secuencia: elegir producto, mover el plazo de entrega,
ver cómo cambia el pedido, abrir la pestaña de integración para mostrar que es la misma llamada
que haría el ERP. Nada más.

Y el cierre, que es de todos pero lo dice una persona:

> «Tres veces en este proyecto llegamos a una conclusión atractiva y le aplicamos una prueba que
> podía tumbarla. Las tres veces la prueba la tumbó: Black Friday, la métrica de error frente a
> la de negocio, y la elasticidad. Ninguna de las tres estaba obligada a hacerse. Creemos que
> ese es el resultado del que estamos más orgullosos.»

- 4 diapositivas: el problema de los cuadernos sueltos · el diagrama del sistema · demo · las tres
  refutaciones.

## La demo, y su plan B

Ensayarla tres veces con el portátil que se vaya a usar y **con el proyector conectado**.

Plan B obligatorio: un vídeo de 60 segundos de la misma secuencia, ya reproducido una vez antes
de empezar para que esté en caché. Si la aplicación no arranca en quince segundos, se pasa al
vídeo sin comentarlo. Nadie del tribunal recuerda una demo que funcionó; todos recuerdan una que
no.

## Banco de preguntas

Se asigna una persona a cada pregunta antes de la defensa. Quien la tenga asignada contesta;
nadie interrumpe a nadie. Respuestas de treinta a cuarenta y cinco segundos.

| # | Pregunta probable | Quién | Respuesta |
|---|---|---|---|
| 1 | Un WRMSSE de 1,04 es peor que 1. ¿Entonces el modelo no sirve? | D | Un WRMSSE de 1 es la naive estacional, que es una referencia dura en series intermitentes. Lo relevante es dónde gana: la simulación de la política muestra un 19,3% de mejora en la cola larga. Y produce intervalos, que la referencia no da y que la reposición necesita. |
| 2 | ¿Por qué no probasteis redes neuronales? | D | Está dimensionado y dejado listo, y la expectativa honesta es que pierda: en la competición M5, con esta misma estructura de datos, ganaron los ensambles de árboles. Con la media móvil de 28 días concentrando el 71,7% de la importancia, el techo lo pone el ruido de la serie, no la arquitectura. |
| 3 | ¿No optimizasteis hiperparámetros? | D | La búsqueda está montada, sobre el pliegue 2 y validando en el 3. Decidimos no incluirla porque el diagnóstico de importancia indicaba una zona plana, y el tiempo rendía más en el planteamiento del problema, que es donde estaba el factor veinte. |
| 4 | ¿Por qué K=5? ¿No es arbitrario? | C | Criterio combinado: silueta, mínimo local de Davies-Bouldin y máximo relativo de Calinski-Harabasz. Y comprobación cruzada: la misma partición sale con Ward y con mezclas gaussianas. Mantenemos además K=10 para campañas, con un propósito distinto y declarado. |
| 5 | En la elasticidad, ¿por qué no variables instrumentales? | D | No encontramos un instrumento defendible: haría falta algo que mueva el precio y no la demanda, como un coste de proveedor, y no está en los datos. Preferimos declarar que no se puede identificar antes que usar un instrumento débil, que da un resultado con apariencia de rigor y sin él. |
| 6 | ¿Por qué DuckDB y no Spark o una plataforma en la nube? | B | Por volumen: 58 millones de filas y 91 MB en consumo se procesan en segundos. Por reproducibilidad: el tribunal puede reconstruirlo sin credenciales. Y porque no cierra la puerta: es SQL estándar sobre Parquet, que es justo lo que ingiere una plataforma de nube. La migración cambia el motor, no la lógica. |
| 7 | El 90% de nivel de servicio, ¿de dónde sale? | D | De ningún sitio, y es una crítica correcta. Lo usamos como referencia. El valor correcto es el ratio crítico, margen entre margen más coste de exceso: con margen 25% y posesión 5% da 0,83, y con un perecedero de merma 20%, 0,50. Está identificado como la corrección más inmediata. |
| 8 | ¿Cómo sabéis que la política mejora si no la habéis desplegado? | D | No lo sabemos: es una simulación sobre demanda observada, y la cifra del 61% es el resultado de un modelo de costes con parámetros supuestos. Por eso presentamos una curva y no un número, y por eso la primera recomendación es medir la merma. |
| 9 | ¿Hay fuga de información en la validación? | D | Es lo primero que revisamos. Validación por avance, nunca aleatoria, y retardo mínimo condicionado al horizonte: el modelo del bloque cuatro no puede usar nada de los últimos veintiocho días. De hecho el resultado incómodo del capítulo salió precisamente de quitar esa fuga. |
| 10 | ¿Qué pasa con un producto nuevo, sin histórico? | C | No está resuelto, y es una limitación real. El modelo es global, así que puede predecir con los atributos del producto y su tienda, pero sin retardos ni medias móviles pierde el 88% de su información útil. Lo razonable sería asignarlo a un arquetipo por similitud de catálogo hasta tener histórico. |
| 11 | ¿Por qué quitasteis Black Friday? | A | Porque no había pico. Lo habíamos metido por expectativa, no por evidencia, y era tentador venderlo como oportunidad desaprovechada. El dato no lo sostenía. No sabemos si es la política comercial, el catálogo o la codificación del calendario, y así lo dejamos escrito. |
| 12 | ¿Cuál es la aportación original? | B | No un método nuevo. Tres cosas: llevar la cadena hasta la unidad pedida y el dinero, en vez de parar en la métrica de error; formular el criterio de selección de modelo como coste de negocio, demostrando su equivalencia con la pérdida pinball en el ratio crítico; y someter cada conclusión a una prueba de falsación, con tres casos en que la prueba nos contradijo. |
| 13 | ¿Y Croston, para la demanda intermitente? | D | Es la referencia obligada y no lo incluimos: la comparación fue entre modelos globales y las familias clásicas generales. Está en trabajo futuro, y es justo el segmento —la cola larga— donde nuestro enfoque aporta menos sobre una regla simple. |
| 14 | ¿Qué haríais con más tiempo? | B | Por retorno esperado y no por sofisticación: cambiar el criterio de selección al coste, predecir el total del ciclo en vez de la suma de días, y registrar la decisión real del encargado, que es el dato que convertiría esto en un sistema que aprende. |

## Preguntas que conviene provocar

Hay tres respuestas que son mejores que sus preguntas. Si nadie las hace, se plantan en el
discurso; si alguien las hace, se contestan con calma porque están preparadas.

1. **El 90% arbitrario.** Reconocer una debilidad antes de que la señalen es la forma más barata
   de credibilidad que existe en una defensa.
2. **La refutación de la Tarea 3 por la Tarea 4.** Es el argumento más fuerte del trabajo y no
   puede quedar sepultado entre dos gráficos.
3. **Que la elasticidad no se pudo estimar.** Presentado como decisión metodológica y no como
   fracaso: distinguir un coeficiente significativo de una identificación creíble es exactamente
   lo que un máster debe enseñar.

## Antes de entrar

- Cronometrar cada intervención por separado, no solo el total. El que se pasa se lo quita al
  siguiente.
- Ensayar las transiciones. Los cambios de persona son donde se pierde el hilo.
- Llevar el PDF en dos memorias USB y en el correo. El portátil no es un plan.
- Nadie corrige a un compañero delante del tribunal. Si algo sale mal, se recoge al final con un
  «quería añadir un dato al punto de antes».
- Si alguien no sabe una respuesta, lo dice. «No lo comprobamos» es una respuesta profesional;
  inventar una cifra delante de un tribunal que ha leído la memoria, no.
