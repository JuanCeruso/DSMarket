## 7.7. De sistema a sistema mantenible: la capa de MLOps

El capítulo anterior describe un sistema que se ejecuta con un comando, comprueba sus datos,
registra sus modelos y vigila su error. Es más de lo que suele entregarse, y sin embargo le
faltaba lo que distingue un sistema que funciona hoy de uno que puede seguir funcionando dentro
de un año sin sus autores. Este capítulo describe esa diferencia y lo que se hizo para cubrirla.

La distinción es útil enunciarla así: **la orquestación responde a «¿se puede volver a
ejecutar?»; MLOps responde a «¿quién decide qué llega a producción, cómo se sabe que sigue
siendo correcto, y cómo se deshace?»**. Son preguntas distintas y necesitan piezas distintas.

### 7.7.1. El fallo que faltaba impedir

Los contratos de datos impiden que datos rotos lleguen al modelo. La monitorización avisa cuando
el error se degrada. Pero había un fallo que ninguna de las dos piezas veía, y es el más caro de
todos porque no produce error ni alerta: **que un modelo peor sustituya en silencio al que
funcionaba**.

Ocurría por construcción. En la versión anterior, `entrenar.py` terminaba escribiendo el
identificador del modelo recién entrenado en el fichero que `predecir.py` lee para saber con qué
modelo predecir. Entrenar y desplegar eran el mismo paso. Un entrenamiento sobre un mes anómalo,
sobre una ventana demasiado corta, o simplemente con un mínimo local desafortunado, pasaba a
producción sin que nadie lo decidiera ni lo supiera. El sistema seguía en verde: los contratos
pasaban —las predicciones eran válidas, solo peores—, y el monitor tardaría cuatro semanas en
verlo, porque el error realizado exige que los días predichos hayan ocurrido.

Cuatro semanas de pedidos calculados con un modelo peor, sin ninguna señal. Ese es el hueco.

### 7.7.2. Trazabilidad: de dónde salió exactamente este modelo

Antes de poder decidir si un modelo entra, hay que poder decir de qué está hecho. El registro de
modelos guardaba hiperparámetros, ventana y métricas, que responde *cuál* es el modelo pero no
*de qué* se hizo. Se añadieron tres huellas, y las tres son necesarias:

**El código.** El SHA del commit con el que se entrenó, y —esto importa— un sufijo explícito
cuando el árbol de trabajo tenía cambios sin comitear. Un modelo entrenado sobre un árbol sucio
no es reconstruible a partir de su SHA, y es mejor que el registro lo diga a que alguien lo
descubra intentando reproducirlo seis meses después.

**Los datos.** Una huella del almacén en el instante del entrenamiento, calculada sobre los
ficheros que el modelo realmente lee. No sirve la fecha: dos entrenamientos del mismo día ven
almacenes distintos si alguien reconstruyó la capa de plata entre medias, y esa es exactamente
la situación en la que uno se pregunta por qué los números no cuadran.

**El entorno.** Versión del intérprete y de las cinco bibliotecas que deciden el resultado
numérico. LightGBM cambia de resultado entre versiones menores; no anotarlo convierte cualquier
comparación de métricas entre dos fechas en una conjetura.

Con las tres, la pregunta «este pedido de hace tres semanas, ¿con qué modelo se calculó?» tiene
por fin respuesta completa: con este modelo, entrenado con este código, sobre este almacén, con
estas versiones.

### 7.7.3. La puerta de promoción

Entrenar dejó de desplegar. Lo que sale del entrenamiento es un **candidato**: queda registrado
con todo lo anterior y no predice nada. Entre el entrenamiento y la predicción se intercaló una
etapa nueva en el orquestador —que pasa de nueve a diez— cuyo único trabajo es decidir si el
candidato desbanca al vigente. Cuatro reglas:

**Cordura absoluta.** La cobertura empírica del percentil 90 debe caer entre el 85% y el 95%. La
banda tiene dos lados a propósito. Un intervalo que cubre el 99% no es prudente: es stock de
seguridad inflado en todo el surtido, y §7.4 cuantifica lo que cuesta esa clase de prudencia.

**No empeorar.** El error absoluto medio del candidato no puede superar al del vigente en más de
un 5%. El margen no es cero, y la razón es empírica: el ruido entre dos ventanas de validación
de cuatro semanas es de ese orden, de modo que una puerta con tolerancia cero rechazaría ruido y
congelaría el sistema en su primer modelo para siempre.

**Reproducibilidad.** Un candidato entrenado sobre un árbol de trabajo sucio genera un aviso, y
con la opción correspondiente, un rechazo.

**Contratos en verde.** Un candidato entrenado sobre datos que no pasan los contratos no se
promueve aunque sus métricas sean excelentes. Probablemente lo sean por eso.

Lo importante es qué ocurre cuando el candidato no pasa: **no falla nada**. El pipeline continúa
y predice con el modelo vigente de siempre. Es el único punto del sistema donde «no hacer nada»
es el resultado correcto, y por eso la etapa está escrita para distinguir entre rechazar —su
trabajo— y fallar —no tener ningún modelo con el que seguir—. El candidato rechazado tampoco se
borra: queda en el registro con el motivo, porque el histórico de lo que no se promovió es la
mitad de la información útil cuando algo va mal.

> **[FIGURA 7.28]** *Ciclo de vida de un modelo: los cuatro estados y las transiciones.*
> `Fuente: Diagrama de elaboración propia. Debe mostrar que entrenar no promueve y que el retroceso es una arista.`

**El retroceso.** Un modelo promovido puede resultar malo de todos modos: la puerta compara
métricas de validación, y la validación describe el pasado. Volver al anterior es un comando que
no reentrena nada —los pesos del modelo retirado siguen en disco, solo cambia el puntero— y
tarda segundos. Esa asimetría es deliberada: **deshacer tiene que ser más barato que
diagnosticar**, porque a las tres de la mañana nadie diagnostica bien.

### 7.7.4. Pruebas automáticas e integración continua

El proyecto tenía doce pruebas sobre el servicio web y ninguna sobre la lógica que decide los
pedidos. Es el reparto habitual y está al revés: un fallo del servicio se ve en el acto, un
error en la fórmula del stock de seguridad se ve cuando falta mercadería.

La razón de que no estuviera probada era estructural, no de desidia: la política vivía dentro
del guion que consulta el almacén, de modo que comprobar que el stock de seguridad crece con el
nivel de servicio exigía reconstruir 163 MB de almacén. Se extrajeron las funciones puras a un
módulo propio. No cambia ningún número; cambia que ahora son comprobables.

La suite tiene **78 pruebas y se ejecuta en poco más de dos segundos**, y —esto es lo que la hace
viable— **no necesita los datos de DSMarket**. Una suite que exige 469 MB de ficheros propiedad
de la escuela es una suite que no se ejecuta nunca. Cubre cinco bloques:

| Bloque | Qué comprueba | Ejemplo de propiedad verificada |
|---|---|---|
| Política de reposición | 20 pruebas | El coste del vendedor de periódicos es la pérdida pinball reescalada |
| Métricas de deriva | 8 pruebas | El PSI detecta un cambio de escala que la media no ve |
| Contratos de datos | 28 pruebas | Cada contrato detecta la violación que dice detectar |
| Puerta de promoción | 13 pruebas | Un candidato peor no pasa la puerta |
| Registro de modelos | 9 pruebas | Entrenar deja un candidato, no un modelo desplegado |

Dos merecen comentario. La prueba de que **C(S) = (Cu + Co) · L_τ*(D − S)** verifica por muestreo
la identidad sobre la que se apoya medio capítulo §7.4: si alguien rompe esa igualdad editando
una fórmula, el argumento de elegir el modelo por coste de negocio deja de ser cierto y la suite
lo dice en el acto.

Y los contratos se prueban construyendo un **almacén de juguete en memoria** —dos productos, dos
tiendas, tres días— que pasa limpio, y rompiéndolo después de una manera distinta cada vez. Un
contrato que nunca ha fallado no está probado: está sin estrenar. Entre esas roturas dirigidas
están los tres defectos reales de §7.6.4 —el cruce de cuantiles, el fin de semana corrido dos
días y el cambio de significado de esa misma bandera entre entrenamiento y predicción—,
convertidos en pruebas de regresión para que no puedan volver en silencio.

Conviene señalar que el almacén de juguete deriva su bandera de fin de semana del nombre del
día, igual que el de verdad. Escribirla ahí como `weekday_int IN (5, 6)` habría reproducido el
defecto dentro de la propia prueba, que entonces habría comprobado que el error es consistente
consigo mismo. Es el modo más común de que una suite verde no signifique nada.

**La integración continua** ejecuta tres trabajos en cada envío de código, ordenados del más
rápido al más lento para que el fallo barato llegue antes: que todo el árbol compile, que la
suite pase —dos veces, en órdenes distintos, porque una prueba que solo pasa en su orden
habitual depende de un estado que no declaró—, y que el orquestador sepa enumerar sus etapas.
El entorno de integración instala seis paquetes, no el entorno completo: las pruebas no entrenan
nada, y añadir tres minutos por ejecución para instalar LightGBM no cubriría una línea más.

### 7.7.5. El lazo cerrado

Hasta aquí el monitor escribía una alerta y la alerta se quedaba ahí, esperando que alguien la
leyera. Eso es un tablero, no un lazo. Un lazo cerrado es cuando la señal vuelve a entrar en el
sistema y cambia lo que el sistema hace.

La política está escrita en un solo sitio y es deliberadamente conservadora. **Se reentrena** si
hay dos ejecuciones consecutivas del monitor en alerta —una sola puede ser un festivo mal
codificado— o si han pasado más de 28 días desde la última promoción, que es el horizonte de
predicción y por tanto el ciclo natural de refresco.

**No se reentrena** si los contratos de datos no están en verde. Es la regla que más veces salva
el sistema, y merece enunciarse entera: si la alerta viene de que los datos cambiaron de forma,
reentrenar produce un modelo nuevo que aprende el error y exhibe unas métricas de validación
excelentes calculadas sobre los mismos datos rotos. El diagnóstico va antes que el remedio.
Tampoco se reentrena si ya se reentrenó hace menos de siete días, porque sin ese límite una
alerta persistente convierte el lazo en un bucle.

Y reentrenar no es promover: lo que sale del lazo es un candidato que sigue teniendo que pasar
por la puerta. **El lazo automatiza el trabajo, no la decisión.**

### 7.7.6. El entorno fijado y la imagen del servicio

`requirements.txt` dice qué hace falta; no dice cuál. `pandas` a secas significa «la versión de
pandas que hubiera el día que lo instalaste», de modo que dos personas siguiendo el mismo manual
pueden acabar con entornos distintos y dos entrenamientos del mismo código pueden dar números
distintos sin que nadie sepa por qué.

Se añadió un fichero de entorno **fijado**, generado y no escrito a mano, con las versiones
exactas; y un modo de comprobación que compara el entorno actual con el fijado y distingue las
diferencias que pueden cambiar los números de las que no. Son dos ficheros porque son dos
propósitos: uno instala el proyecto, el otro lo reproduce.

El servicio de reposición se empaqueta además en una **imagen de contenedor** que fija el sistema
operativo, la versión menor del intérprete y las dependencias. Resuelve de paso, y de una vez,
el mismo problema de OpenMP que aparece en macOS. La imagen contiene el código y no los datos:
el almacén se monta como volumen y en solo lectura, lo que es correcto —el servicio lee, nunca
escribe— y evita redistribuir unos datos que no son nuestros. Sus dependencias son siete y no
veinticinco: una imagen del servicio no necesita Jupyter, Prophet ni Matplotlib, y separarlas es
la diferencia entre 1,5 GB y 400 MB.

### 7.7.7. Por qué no MLflow, Airflow ni Kubeflow

Es la objeción previsible y conviene responderla de frente, porque la respuesta no es que se
desconozcan.

Las herramientas del ecosistema resuelven tres problemas reales: **escala** —cientos de
experimentos, decenas de personas, cómputo distribuido—, **colaboración** —un registro
compartido al que varios equipos escriben— e **integración** con plataformas gestionadas. Este
proyecto tiene un equipo de cuatro personas, un almacén de 91 MB en su capa de consumo y un
pipeline de nueve minutos. Ninguno de los tres problemas se presenta.

Frente a eso, adoptarlas tiene un coste concreto en el contexto de un trabajo académico: un
tribunal debe poder reconstruir el sistema entero en su máquina sin levantar un servidor de
seguimiento, una base de datos de metadatos ni un planificador. El registro de modelos de este
proyecto es una tabla Parquet en el mismo almacén que el resto de los datos, lo que tiene una
ventaja que no es menor: **las métricas del sistema se consultan con el mismo SQL que los datos
de negocio**, y el cuadro de mando puede mostrarlas sin integración adicional.

La respuesta honesta, por tanto, no es que estas herramientas sobren, sino que **lo que se
implementó son las funciones que ellas ofrecen, en la escala que este problema tiene**: registro
con procedencia, promoción con puerta, retroceso, monitorización con umbrales y orquestación con
reanudación. Y por eso la migración, si algún día procede, es un cambio de implementación y no de
diseño: los conceptos ya están separados y nombrados. Lo que haría falta para justificarla está
enunciado en §7.7.8.

### 7.7.8. Dónde queda el sistema, y qué sigue faltando

Situar el trabajo con honestidad exige decir también lo que no está.

| Capacidad | Estado | Nota |
|---|---|---|
| Ejecución reproducible de punta a punta | Implementada | Un comando, diez etapas, reanudable |
| Contratos de datos bloqueantes | Implementada | 15 contratos, en dos pasadas |
| Registro de modelos con procedencia | Implementada | Código, datos y entorno |
| Promoción con puerta y retroceso | Implementada | Entrenar no despliega |
| Monitorización de error y deriva | Implementada | Tres señales de naturaleza distinta |
| Pruebas automáticas e integración continua | Implementada | 78 pruebas, sin datos |
| Entorno fijado y servicio en contenedor | Implementada | Dos ficheros, dos propósitos |
| Reentrenamiento por señal, con política | Implementada | Asistido: propone, no decide |
| Realimentación con la decisión humana | **Ausente** | El dato no existe; §7.6.8 |
| Contraste A/B en explotación | **Ausente** | Requiere la fase 2 del despliegue |
| Autenticación y control de acceso | **Ausente** | Aceptable en prototipo, no en explotación |
| Repositorio de variables compartido | **Ausente** | No se justifica con un solo consumidor de modelos |
| Servicio a escala y alta disponibilidad | **Ausente** | Diez tiendas caben en memoria |

Las cuatro ausencias no son accidentales y tres de ellas comparten causa: dependen de que el
sistema esté en explotación. La primera es la más importante, y ya estaba señalada en §7.6.8:
**mientras no se registre qué pidió realmente el encargado frente a lo que el sistema sugirió,
no hay forma de medir si el sistema acierta**. Todo lo descrito en este capítulo sirve para que
el día que ese dato exista, el sistema pueda usarlo sin reescribirse.
