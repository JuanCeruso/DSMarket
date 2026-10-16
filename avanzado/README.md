# Experimentos avanzados

Nueve experimentos y sondeos que no hacen falta para aprobar el TFM y que pueden mejorarlo. **No están
ejecutados**: la máquina donde se escribieron tiene 3,8 GB de RAM y estos scripts piden más.
En tu Mac, con 24 GB, corren sin problema.

Todos leen del lakehouse (`lakehouse/gold/`), no de ficheros temporales, así que siguen
funcionando aunque se borre cualquier caché. Colocá esta carpeta como `PROYECTO/avanzado/` y
ejecutá desde `PROYECTO/`.

---

> **Nota (octubre 2026).** Estos experimentos se ejecutaron con la versión anterior del modelo:
> 180 días de historia y la segmentación anterior de la Tarea 2 (cluster_k5, cluster_k10 y grupos
> de tienda). El código compartido (`comun.py`) ya usa la configuración final —400 días en
> `operacion/entrenar.py`, el grupo de producto actual y las variables de evento semanal—, así que
> si se vuelven a ejecutar los resultados pueden cambiar ligeramente respecto a los de
> `resultados/`. El experimento 8 (arranque en frío) sí se volvió a ejecutar con la versión final.

## La respuesta corta a «¿hay algo más avanzado que probar?»

**Sí, pero no donde uno esperaría.** El diagnóstico de la Tarea 3 es el que manda: la media
móvil de 28 días concentra el **71,7%** de la importancia del modelo, y las cuatro medias
móviles juntas el 88%. Un modelo con más capacidad no tiene de dónde sacar señal adicional —
el techo lo pone el ruido de una serie que vende dos unidades por día, no la arquitectura.

Por eso el orden de abajo no está por sofisticación sino por **retorno esperado**. Y los dos de
arriba no son modelos: son **cambios de criterio**. El 7 declara un sesgo que hoy no se declara y
el 5 cambia la función con la que se elige. Ninguno añade una línea de capacidad al modelo, y los
dos cambian más las conclusiones que cualquier arquitectura nueva.

Si solo hay tiempo para dos, son el 7 y el 5.

| # | Experimento | Coste | Ganancia esperada | Por qué |
|---|---|---|---|---|
| 5 | **Elegir el modelo por coste, no por error** | ~45 min | **Muy alta** | Cambia el criterio de decisión, que es la raíz del problema |
| 2 | Predecir el total del ciclo | ~30 min | Alta | Cambia el planteo del problema, no el modelo |
| 4 | Predicción conforme | ~10 min | Media | Convierte una cobertura empírica en garantía formal |
| 1 | Búsqueda de hiperparámetros | ~1 h | Baja (1-2%) | Estándar de oficio; el tribunal puede preguntarlo |
| 3 | Redes neuronales | 1-2 h | Probablemente nula | Resultado publicable aunque pierda |
| 6 | Sondeo de afinidad entre productos | ~2 min | **Decide, no mejora** | Dice en dos minutos si hay capítulo o hay párrafo |
| 7 | **Acotar la demanda censurada** | ~5 min | **Muy alta** | Es el agujero que un tribunal bueno va a encontrar |
| 8 | Arranque en frío | ~5 min | Media | Un problema real de retail que el proyecto no resuelve |
| 9 | Surtido: candidatas a descatalogar | ~1 min | Media | Responde la pregunta que la matriz ABC/XYZ deja abierta |

Los experimentos 5 y 2 se refuerzan: el 5 dice **con qué criterio** elegir y el 2 **sobre qué
objetivo** entrenar. Hechos juntos, el modelo se entrena sobre el total del ciclo con la pérdida
pinball en el ratio crítico, que es exactamente la cantidad que se usa para decidir y exactamente
la función que el negocio paga. Si hay tiempo para dos, son esos dos.

---

---

## 6 · Sondeo: ¿hay afinidad real entre productos?

```bash
python3 avanzado/06_afinidad_sondeo.py --tiendas BOS_1 NYC_1
```

**Esto no es un experimento, es un sondeo: cuesta dos minutos y su única función es decidir si
vale la pena escribir una sección.** Córrelo antes de invertir tiempo en el tema.

Lo primero que hay que tener claro: **no tenemos datos de cesta**. `item_sales.csv` viene
agregado por producto-tienda-día; no hay ticket, no hay transacción, no hay cliente. Un market
basket analysis de verdad —soporte, confianza, lift, reglas de asociación— necesita la cesta.
Cualquier resultado presentado como «estos productos se compran juntos» sería una afirmación
que el dato no sostiene.

Lo que sí se puede medir es **afinidad de demanda**: productos cuya venta sube y baja los mismos
días en la misma tienda. Y tiene una trampa que invalida la versión ingenua — casi todo el
co-movimiento diario lo explica el sábado, diciembre, un evento o el tráfico de la tienda. El
script residualiza contra todo eso (el mismo movimiento que la Tarea 5) y mide el co-movimiento
sobre lo que queda.

Las tres pruebas, en orden de importancia:

1. **Nulo entre tiendas.** El producto A de una tienda con el B de otra nunca pueden compartir
   cesta: esa distribución es el nivel de ruido. **Esta es la prueba que decide.** Si las
   parejas de la misma tienda no superan su percentil 99 por encima del 1% esperable por azar,
   no hay nada que contar.
2. **Nitidez temporal.** Una compra conjunta es del mismo día; si aguanta al desplazar una serie
   un día, era tendencia compartida. Ojo: esta prueba *no* separa señal de ruido por sí sola
   —dos series independientes también son «nítidas»—, solo describe cómo son las mejores parejas.
3. **Estabilidad fuera de muestra.** Se eligen con el 70% inicial de los días y se comprueban en
   el 30% final. Con 20.000 parejas, las mejores por azar siempre salen altas.

Si sale señal, la sección va en §7.2 y hay que escribirla como **afinidad de demanda, no compra
conjunta**, cerrando igual que la Tarea 5: con un candidato y una promoción cruzada aleatorizada
como diseño de validación. Si no sale, es un párrafo de conclusiones más una recomendación
concreta a DSMarket —incorporar el identificador de ticket al registro de ventas—, que es
exactamente el tipo de resultado negativo que esta memoria ya sabe presentar bien.

---

## 7 · Acotar la demanda censurada

```bash
python3 avanzado/07_censura_cota.py
```

**Correlo antes que ningún otro.** No mejora nada; declara un límite que hoy el trabajo no
declara, y ese límite es la crítica más fuerte que se le puede hacer.

`fact_ventas` registra unidades **vendidas**, no demandadas. Si una tienda se quedó sin stock,
ese día es un cero indistinguible de un día sin demanda. Consecuencias: el modelo se entrena con
demanda censurada y **predice por debajo**; y la simulación de la Tarea 4 calcula el faltante con
ventas que ya excluyen lo perdido, así que los 161.353 USD son una **cota inferior**.

Sin datos de inventario no se corrige, solo se acota. El script separa los ceros por
verosimilitud —un cero con intensidad esperada alta es sospechoso— y construye dos cotas. La
prueba que lo valida es que **una rotura dura días y el ruido de Poisson no**: compara la
distribución de longitudes de racha con la esperable por azar.

Lo bueno: el resultado **refuerza** la conclusión del proyecto. Si con la medición conservadora
ya se pierden catorce dólares por cada uno inmovilizado, la realidad es peor. Poder decir en la
defensa «conocemos el sesgo, sabemos su dirección y va a favor de nuestra recomendación» vale más
que un modelo nuevo.

## 8 · Arranque en frío

```bash
python3 avanzado/08_arranque_frio.py
```

El 88% de la importancia del modelo está en las medias móviles, y un producto nuevo no las tiene.
El sistema no puede decir cuánto pedir justo cuando más falta hace acertar.

Predice la demanda media del producto nuevo con lo que sí existe el día del alta —categoría,
departamento, tienda, precio— aprendiendo de las series que sí tienen historia, y lo compara con
lo que haría un encargado: la media de la categoría en esa tienda, la del departamento, y la
misma referencia en la tienda más parecida.

Lo difícil no es entrenar, es **evaluar sin hacer trampa**: la partición es por producto, no por
fila, de modo que ningún producto de prueba aparece en el entrenamiento en ninguna tienda.

Resultado con la versión final: copiar la misma referencia de la tienda más parecida tiene un MAE
de 0,918 unidades/día, un 34,6% mejor que la media de la categoría (1,404) y mejor que el modelo
por atributos (1,028, con un sesgo del −27%). Esa vía gana, y eso conecta con el
hallazgo de §7.2 —el parecido entre tiendas cruza las fronteras de ciudad—. La comparación de
tiendas no era descriptiva: sirve para decidir de qué tienda copiar. La tienda vecina es la más
parecida según la Tarea 2 (sección 5.3), que el almacén guarda en `dim_tienda.tienda_mas_parecida`.

## 9 · Surtido: candidatas a descatalogar

```bash
python3 avanzado/09_surtido.py --top 100
```

DSMarket no hizo esta pregunta, pero es la consecuencia directa de la matriz ABC/XYZ: la celda CZ
es el 28% del catálogo por el 3,5% de la facturación.

Vender poco no basta para retirar una referencia. Se combinan cinco señales, y **dos son frenos**:
si es de las pocas referencias de su departamento en esa tienda, no se toca; si en esa tienda
concreta rota mejor que en el resto de la red, tampoco. Esos dos frenos evitan el error clásico
—descatalogar el único producto de una familia— que un ranking por facturación comete siempre.

El script enseña además cuánto se solapa con ese ranking simple: la diferencia son exactamente
las referencias que no hay que tocar.

Y lo que no es: una decisión. Sin margen por referencia, coste de lineal ni sustitución, esto
ordena 30.490 series para que alguien mire cincuenta. Nada más, y es bastante.

## 5 · Elegir el modelo por su coste, no por su error

```bash
python3 avanzado/05_seleccion_por_coste.py
python3 avanzado/05_seleccion_por_coste.py --margen 0.25 --merma 0.10
```

**El que yo correría primero, por delante del 2.** Hoy el modelo se elige con WRMSSE: una métrica
simétrica, que penaliza igual pasarse que quedarse corto. A DSMarket no le cuesta lo mismo. La
métrica con la que se elige debería ser el coste, y el proyecto ya tiene el simulador para
calcularlo.

Lo que hace defendible el cambio es que no es un capricho de negocio: el coste esperado del
*newsvendor* **es** la pérdida pinball evaluada en el ratio crítico τ* = Cu/(Cu+Co), salvo una
constante. O sea que la métrica de negocio tiene un equivalente estadístico exacto —y de paso
revela que el 0,90 uniforme que usamos es un número puesto a ojo: con margen 25% y merma 5%, el
τ* correcto es 0,83.

El script compara cinco candidatos sobre el mismo fold y los ordena por MAE, por WRMSSE y por
coste. Mira tres cosas:

1. **Si los tres ranking coinciden.** Si coinciden, es un resultado tranquilizador y publicable.
2. **Si gana el mismo candidato en todos los segmentos ABC/XYZ.** Casi seguro que no, y eso
   confirma por otra vía lo que ya encontró la Tarea 4.
3. **La tabla de sensibilidad.** Un ganador que cambia al mover el supuesto de merma es un
   ganador frágil, y decirlo en la defensa vale más que presentar un número redondo.

Ya tenemos un indicio fuerte de que los ranking no coinciden: la simulación de la Tarea 4
invirtió la conclusión de la Tarea 3 sobre dónde aporta el modelo: ahorra más justo en la demanda
irregular, donde peor error de predicción tiene. Este experimento generaliza ese hallazgo de una comprobación a
posteriori a un **criterio de selección**.

## 1 · Búsqueda de hiperparámetros con Optuna

```bash
pip install optuna
python3 avanzado/01_tuning_optuna.py --pruebas 40
```

Busca sobre el fold 2 y **valida en el fold 3**, que no participó de la búsqueda. Esa
separación es lo que hace creíble la mejora: optimizar y medir en el mismo período sería
ajustar el modelo a ese mes concreto.

Si la mejora sale por debajo del 1%, la conclusión honesta para la memoria es que el modelo
ya estaba en una zona plana. Es un resultado, no un fracaso.

## 2 · Predecir el total del ciclo, no cada día

```bash
python3 avanzado/02_objetivo_agregado.py
```

**El que yo correría primero.** La idea no es de modelado sino de encuadre: la política de
reposición no necesita saber cuánto se vende cada día, necesita el **total de los nueve días**
que dura el ciclo. Hoy sumamos nueve predicciones diarias y arrastramos nueve errores. Un
modelo entrenado directamente sobre ese total tiene un objetivo menos ruidoso —agregar
promedia el ruido— y optimiza exactamente la cantidad que se usa para decidir.

De paso prueba el ensamble LightGBM + XGBoost, que cuesta cinco líneas.

Si gana, la frase para la memoria es buena: *el error no venía del modelo sino de cómo estaba
planteado el objetivo.*

## 3 · NHITS y Temporal Fusion Transformer

```bash
pip install "neuralforecast>=1.7" torch
python3 avanzado/03_deep_learning.py --series 1000
```

Usa la GPU integrada del Mac (PyTorch MPS) automáticamente. Sobre 1.000 series tarda entre 40
y 90 minutos; con las 30.490 haría falta una GPU dedicada.

**Expectativa honesta:** en la competición M5 —que tiene exactamente esta estructura de
datos— ganaron los ensambles de árboles, no las redes. Lo más probable es que LightGBM gane
también acá, y eso está bien: poder escribir «probamos las arquitecturas de referencia y
confirmamos el hallazgo de la literatura con nuestros propios datos» es más sólido que no
haberlo probado.

Lo que sí merece mirarse aparte es la **cobertura del intervalo**: el TFT devuelve cuantiles
de forma nativa, y si calibra mejor que nuestro modelo cuantílico, eso sí sería un argumento
para usarlo en la parte de abastecimiento.

## 4 · Predicción conforme

```bash
python3 avanzado/04_conformal.py
```

Nuestro p90 dio una cobertura del 90,0% frente a un objetivo del 90%. Excelente, pero
**empírico**: salió bien esa vez. La predicción conforme lo convierte en una garantía formal
de cobertura en muestra finita, sin asumir ninguna distribución.

Calibra sobre el fold 2 y evalúa en el fold 3. Mirá sobre todo la cobertura por clase XYZ: lo
habitual es que la clase Z —la demanda errática— sea donde el modelo sin ajustar se queda
corto, y es justo donde la garantía tiene valor.

---

## Lo que NO vale la pena, y por qué

**Más ingeniería de variables sobre el precio.** Lo descartamos con evidencia en la Tarea 5:
los precios se mueven en el 1,1% de las semanas y cuando se mueven no lo hacen al azar. No hay
señal que extraer.

**Un LightGBM más grande.** Más hojas o más árboles sin cambiar nada más entra en zona de
rendimientos decrecientes. La búsqueda del experimento 1 ya cubre ese espacio de forma ordenada.

**LSTM o GRU genéricas.** Fueron superadas por NHITS y TFT en su propio terreno. Si vas a
gastar tiempo en redes, gastalo en las del experimento 3.

**Reentrenar con los cinco años completos.** Aquí había escrito que no hacía falta, porque
`rmean_364` ya le da al modelo la referencia anual. **Era un error.** En la Tarea 3 (sección 16.5)
se probó entrenar con 400 días en lugar de 180 y diciembre mejoró un 5,7 %: con 180 días el modelo
nunca ha visto una Navidad cuando predice diciembre, y `rmean_364` no basta para que aprenda el
cierre del día 25. El modelo final se entrena con 400 días. Lo que sigue sin estar probado es si
los cinco años completos aportan algo más que 400 días.

---

## Qué hacer con los resultados

Los nueve scripts escriben en `avanzado/resultados/`. Sea cual sea el resultado, **entra en la
memoria**: si mejoran, como refinamiento del modelo final; si no, como sección de
«alternativas evaluadas y descartadas», que es exactamente lo que distingue un trabajo que
exploró el espacio de uno que se quedó con la primera opción que funcionó.
