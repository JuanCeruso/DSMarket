## 7.3. Cuánto vamos a vender

> «¿Sigue siendo válido sumar las predicciones individuales para obtener las de los niveles
> agregados?»
> — Paul Rogers, director financiero

Este es el capítulo más técnico del trabajo y el que exige más honestidad, porque su primer
resultado relevante es negativo: con la formulación ingenua del problema, ninguno de los modelos
ensayados supera a una media móvil.

### 7.3.1. Diseño de la comparación

Se compararon cuatro familias de modelos bajo el protocolo único descrito en §6.5: validación
*walk-forward* de tres pliegues, ventana de entrenamiento de 180 días, horizonte de 28 días y
evaluación sobre las 30.490 series.

- **Referencias ingenuas**: último valor, media móvil de 28 días y naive estacional semanal.
- **Modelos globales de árboles**: LightGBM y XGBoost, entrenados sobre todas las series a la vez
  con la serie como variable categórica.
- **Descomposición aditiva**: Prophet, ajustado por serie sobre una submuestra representativa.
- **Estadístico clásico**: SARIMA, igualmente por serie sobre submuestra.

La distinción entre modelos **globales** y **locales** es la decisión de diseño más importante
del capítulo. Un modelo local ajusta parámetros a una sola serie y no puede aprender nada de las
demás; con series que venden dos unidades diarias, eso significa estimar sobre muy poca señal.
Un modelo global aprende un único conjunto de parámetros sobre las 30.490 series a la vez y
comparte la información entre ellas: lo que aprende de una referencia de alta rotación sobre el
efecto del fin de semana lo aplica a una de cola larga que por sí sola nunca lo habría mostrado.
Este es el enfoque que domina la práctica reciente en previsión minorista a gran escala, y es el
que el trabajo adopta como principal; Prophet y SARIMA se conservan como contraste de familia,
no como candidatos serios a la escala del problema.

### 7.3.2. El resultado incómodo

Con la estrategia de predicción ingenua —un solo modelo que predice los veintiocho días con la
información disponible hasta el día anterior—, **los modelos de aprendizaje automático no
superan a la media móvil de 28 días en error absoluto medio**. El resultado se repite en los
tres pliegues.

La explicación no es que los modelos estén mal ajustados. Es que la formulación del problema les
está dando una ventaja informativa que en explotación no existe: el retardo de un día no está
disponible cuando se predice a veintiocho. Cualquier evaluación que lo permita mide un problema
distinto del que se quiere resolver.

### 7.3.3. La estrategia de horizonte, que es lo que cambia el resultado

Reformulado el problema con la **estrategia por bloques semanales** descrita en §6.4.2 —cuatro
modelos con retardos mínimos de 7, 14, 21 y 28 días— la comparación se invierte y aparece una
ventaja real sobre las referencias. El mejor resultado corresponde a LightGBM con objetivo
Tweedie y estrategia por bloques, con un **WRMSSE de 1,0414**.

> **[FIGURA 7.10]** *Estrategia de predicción por bloques semanales.*
> `Fuente: Diagrama de elaboración propia: los cuatro modelos y sus retardos mínimos.`

El hallazgo metodológico del capítulo es la magnitud relativa de los dos efectos: **la estrategia
de horizonte pesó aproximadamente veinte veces más que la elección de biblioteca**. La diferencia
entre LightGBM y XGBoost, con el mismo planteamiento, es marginal; la diferencia entre plantear
el problema de forma recursiva o por bloques es lo que decide si hay modelo o no lo hay.

Un WRMSSE ligeramente superior a 1 merece una lectura precisa y no complaciente: significa que,
ponderando por facturación, el modelo se comporta de forma comparable a la referencia ingenua
estacional sobre el conjunto de las series. La ventaja del modelo no está en batir esa
referencia de forma uniforme, sino en dónde la bate —el capítulo §7.4 muestra que esa
distribución importa más que el promedio— y en que produce, además, intervalos de predicción que
la referencia no da.

> **[FIGURA 7.11]** *Error de los modelos comparados, por pliegue de validación.*
> `Fuente: Cuaderno 03. Incluir las referencias ingenuas para que la comparación sea legible.`

### 7.3.4. Qué mira el modelo

El análisis de importancia de variables arroja un resultado que conviene no maquillar: la media
móvil de 28 días, `rmean_28`, concentra el **71,7%** de la importancia total, y las cuatro medias
móviles juntas, alrededor del **88%**.

Esta observación se sometió a prueba con una búsqueda de hiperparámetros sobre un pliegue,
validada en otro que no participó en la búsqueda. La configuración afinada **no mejoró**: WRMSSE
de 0,9788 en la original frente a 0,9790 en la afinada, una diferencia de signo negativo y
magnitud despreciable, con una mejora del 1,4% en error absoluto medio como única ganancia. El
modelo estaba, en efecto, en una zona plana del espacio de configuraciones, y el margen de mejora
no estaba ahí.

La lectura correcta es que el modelo está haciendo, esencialmente, una media móvil corregida por
calendario, segmento y precio. Y esa lectura tiene una consecuencia práctica que se documenta en
la sección de trabajo futuro: no hay margen para que un modelo de mayor capacidad extraiga señal
adicional, porque el techo lo pone el ruido de una serie que vende dos unidades diarias, no la
arquitectura del modelo.

> **[FIGURA 7.12]** *Importancia de las variables del modelo final.*
> `Fuente: Cuaderno 03. Quince variables principales; rmean_28 destacada.`

### 7.3.5. Dónde falla: la temporada alta

El diagnóstico por período reveló el fallo más grave del modelo. En el pliegue que incluye
diciembre, la predicción para el día de Navidad fue de **36.704 unidades** frente a **14
reales**.

La causa es estructural y no un error de programación: la ventana de entrenamiento de 180 días
que precede a diciembre no contiene ninguna Navidad, de modo que el modelo no dispone de
información alguna sobre el cierre de los establecimientos ni sobre el desplome de demanda de
ese día. Ninguna variable del conjunto se lo indica.

La corrección adoptada no es de modelado sino de calendario: una **regla de cierre** que anula la
predicción en los días marcados como cierre en `dim_calendario`. Su efecto es medible y
sustancial: el WRMSSE del pliegue pasa de **1,1111 a 1,0805**. Es la confirmación de un
principio general del trabajo —cuando la información necesaria no está en los datos de
entrenamiento, la solución es introducirla como conocimiento del dominio, no esperar que el
modelo la infiera.

> **[FIGURA 7.13]** *Demanda real y predicha en diciembre, antes y después de la regla de cierre.*
> `Fuente: Cuaderno 03. El día de Navidad debe quedar señalado.`

### 7.3.6. Intervalos de predicción

La reposición no necesita saber cuánto se venderá en promedio, sino cuánto podría venderse en el
peor caso razonable. Se entrenó por ello un segundo conjunto de modelos con **regresión
cuantílica** al percentil 90, minimizando la pérdida pinball descrita en §6.6.1.

La calibración resultó ser buena: la **cobertura empírica del percentil 90 fue del 90,0%** frente
a un objetivo del 90%. El contraste con la predicción media es lo que justifica el esfuerzo: la
predicción media cubre únicamente el **67,8%** de las observaciones, de modo que dimensionar el
inventario con ella produciría rotura en una de cada tres ocasiones.

La calibración se sometió además a una comprobación adicional. Una cobertura empírica correcta
lo es sobre la ventana en que se midió, y nada garantiza que lo siga siendo. La **predicción
conforme** convierte esa observación en una garantía de cobertura en muestra finita sin
supuestos distribucionales: se calibra el error de conformidad sobre un pliegue que el modelo no
vio y se corrige el cuantil con él. El resultado confirma la calidad del modelo original —la
cobertura pasa del **89,90% al 90,46%** y el intervalo se ensancha apenas 0,02 unidades— y por
clase de predictibilidad la corrección se concentra donde cabía esperarla: X 89,73→89,85,
Y 89,22→89,78, Z 90,96→91,80. Lo que se gana no es precisión sino **rigor**: un compromiso de
nivel de servicio respaldado por una garantía formal y no por una observación afortunada.

El precio de esa cobertura también se cuantificó, y no es menor: pasar del 68% al 90% de nivel de
servicio exige un **127% más de inventario**. La decisión de dónde situarse en esa curva no es
estadística sino económica, y se resuelve en §7.4.

> **[FIGURA 7.14]** *Cobertura empírica del intervalo frente al nivel nominal.*
> `Fuente: Cuaderno 03. Curva de calibración con la diagonal de referencia.`

### 7.3.7. Calibración del sesgo

Se examinó si la predicción presenta un sesgo sistemático susceptible de corrección. El cociente
entre demanda real y predicha resultó ser **1,074** en el primer pliegue y **1,021** en los dos
siguientes.

La conclusión relevante no es la magnitud del sesgo sino su **inestabilidad**: un factor de
corrección estimado sobre los tres pliegues conjuntamente empeoraría la predicción en dos de
ellos. La calibración, por tanto, se aplica únicamente con la ventana más reciente, y se
recalcula en cada ejecución. Un sesgo que no es estable no es un parámetro, es una condición
del momento.

### 7.3.8. La respuesta a la pregunta del director financiero

La pregunta de si los agregados pueden obtenerse sumando las previsiones individuales se
respondió de forma empírica sobre los seis niveles de la jerarquía: serie, producto, tienda,
ciudad, categoría y total.

Se compararon tres enfoques. **Ascendente** (*bottom-up*): predecir cada serie y sumar.
**Descendente** (*top-down*): predecir el total y repartirlo por proporciones históricas.
**Reconciliación óptima** con el método MinT: obtener predicciones independientes en todos los
niveles y proyectarlas sobre el subespacio de las previsiones coherentes, minimizando la
varianza del error de reconciliación.

El resultado es que **MinT supera al enfoque ascendente en los seis niveles**, con una mejora del
error porcentual absoluto medio del **15,12% al 13,71%**, es decir, una reducción relativa del
**9,3%**.

La respuesta a Paul Rogers tiene por tanto dos partes. La primera: sumar las previsiones
individuales es un procedimiento válido y claramente preferible a modelar cada nivel por
separado sin más. La segunda: reconciliar es mejor que sumar, y añade una propiedad que el
director financiero valorará más que el punto de error —**la coherencia garantizada**. Con
reconciliación, la suma de las previsiones de las tiendas de una ciudad es exactamente la
previsión de esa ciudad, y el informe de dirección no puede contradecir al de operaciones.

> **[FIGURA 7.15]** *Error porcentual absoluto medio por nivel de la jerarquía: ascendente frente a MinT.*
> `Fuente: Cuaderno 03. Barras agrupadas por los seis niveles.`

### 7.3.9. El objetivo correcto no es el día, es el ciclo

Las secciones anteriores predicen la demanda de cada día y después la política de §7.4 suma los
nueve días que cubre un pedido. Esa cadena arrastra nueve errores para producir una sola cifra, y
la cifra que la decisión necesita es únicamente el total. La pregunta que se desprende es si
conviene predecir directamente ese agregado.

Se entrenó por tanto un modelo cuyo objetivo es el **total del ciclo** en lugar de la venta
diaria, sobre los mismos datos y la misma validación:

| Enfoque | MAE | RMSE | Sesgo |
|---|---|---|---|
| Suma de nueve predicciones diarias | 4,731 | 12,255 | **−7,41%** |
| Modelo del total (LightGBM) | 4,061 | 9,666 | +0,32% |
| Modelo del total (XGBoost) | 3,989 | 9,688 | +0,08% |
| **Ensamble de ambos** | **3,986** | **9,457** | +0,20% |

La mejora del error absoluto medio es del **15,7%**, pero el resultado relevante es la última
columna: el sesgo pasa de **−7,41% a +0,20%**. Sumar predicciones diarias no solo acumulaba
error, acumulaba error *en una dirección*, infravalorando sistemáticamente la demanda del ciclo
—y por tanto el pedido.

La lectura metodológica es la misma que atraviesa el capítulo: **el error no venía del modelo
sino de cómo estaba planteado el objetivo**. Agregar promedia el ruido y, sobre todo, entrena
exactamente sobre la cantidad que se usa para decidir.

### 7.3.10. Productos sin histórico

Una referencia recién incorporada al catálogo no tiene retardos ni medias móviles, es decir,
carece del 88% de la información que el modelo utiliza. Es además el momento en que un error de
dimensionamiento resulta más caro. Se evaluaron por ello cuatro formas de estimar su demanda
media, sobre un conjunto de productos ocultados por completo —en todas las tiendas— durante el
entrenamiento:

| Procedimiento | MAE | Mejora sobre la referencia |
|---|---|---|
| **Misma referencia en la tienda del mismo grupo** | **0,838** | **39,4%** |
| Modelo por atributos (categoría, departamento, tienda, precio) | 0,947 | 31,5% |
| Media del departamento en la tienda | 1,327 | 4,1% |
| Media de la categoría en la tienda (referencia) | 1,383 | — |

El resultado interesante es que **la vía más simple gana al modelo**. Y su interés no es la
diferencia de error sino lo que valida: el agrupamiento de tiendas de §7.2.5 no era una
descripción, es un instrumento operativo — dice de qué establecimiento copiar cuando llega un
producto nuevo, y funciona mejor que un modelo entrenado con los atributos del producto.

Ambos procedimientos comparten una limitación que hay que declarar: infravaloran de forma
apreciable, con un sesgo del **−18,2%** en la vía por tienda vecina y del **−25,2%** en la del
modelo. Cualquiera de los dos requeriría calibración antes de su uso.

### 7.3.11. Límites reconocidos

El capítulo deja tres problemas abiertos, que se recogen en las conclusiones y en la propuesta
de trabajo futuro:

1. **Temporada alta.** La regla de cierre corrige el caso extremo, pero el comportamiento del
   modelo en diciembre sigue siendo el peor del año. Una ventana de entrenamiento que incluyera
   el mismo período del año anterior es la vía natural, con el coste de cómputo que conlleva.
2. **Cola larga.** En las series de demanda errática el modelo aporta poco sobre una regla
   simple. Los métodos específicos para demanda intermitente son la referencia obligada.
3. **Sesgo inestable.** La corrección con la ventana reciente es una solución práctica, no una
   explicación de por qué el sesgo se mueve.

### 7.3.12. Qué abre el capítulo siguiente

El capítulo entrega una previsión media, una previsión al percentil 90 y una garantía de
coherencia entre niveles. Nada de eso repone una sola unidad. La pregunta siguiente es qué se
hace con estos números.
