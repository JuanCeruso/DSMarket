# Experimentos avanzados

Nueve experimentos y sondeos complementarios al trabajo principal. Todos leen del almacén
(`lakehouse/gold/`) y se ejecutan desde la raíz del proyecto; los resultados se escriben en
`avanzado/resultados/`. Los scripts requieren más de 3,8 GB de memoria.

> **Nota sobre la versión del modelo.** Los experimentos se ejecutaron con la versión anterior del
> modelo (180 días de historia y la segmentación previa). El código compartido (`comun.py`) usa ya
> 400 días de historia y variables de evento semanal, pero, a diferencia del modelo final,
> conserva la variable de grupo de producto, de modo que una nueva ejecución puede diferir ligeramente de los ficheros de `resultados/`. El
> experimento 8 (arranque en frío) sí se ejecutó con la versión final.

## Criterio de orden

El diagnóstico del modelo condiciona el orden: la media móvil de 28 días concentra el 58,2 % de la
importancia y las cuatro medias móviles juntas el 86 %. Un modelo con más capacidad dispone de poca
señal adicional; el techo lo fija el ruido de series que venden pocas unidades por día. Por ello los
experimentos se ordenan por retorno esperado, no por sofisticación, y los dos primeros son cambios
de criterio (qué se declara y cómo se elige), no de arquitectura.

| # | Experimento | Resultado | Destino en la memoria |
|---|---|---|---|
| 5 | Selección del modelo por coste en lugar de por error | El nivel de servicio uniforme del 90 % resulta 2,45 veces más caro que el óptimo | §7.4 |
| 2 | Objetivo agregado (total del ciclo) | MAE de 4,73 a 3,99 (−15,7 %); sesgo de −7,4 % a +0,2 % | §7.3 |
| 7 | Acotación de la demanda censurada | Entre 4,79 % y 14,83 % de unidades no observadas | §6.2.4 y §7.4.7 |
| 4 | Predicción conforme | Cobertura del 89,9 % sin ajustar y del 90,5 % con garantía formal | §7.3 |
| 1 | Búsqueda de hiperparámetros (Optuna) | WRMSSE de 0,9788 (original) y 0,9790 (afinada): zona plana | Anexo G |
| 6 | Afinidad de demanda entre productos | Sin señal por encima del ruido entre tiendas distintas | §7.2.6 |
| 8 | Arranque en frío | Copiar la referencia de la tienda más parecida: MAE de 0,918, un 34,6 % mejor que la media de la categoría | §7.8 |
| 9 | Surtido: candidatas a descatalogar | Ranking de la celda CZ con dos frenos de seguridad | §7.8 |
| 3 | Redes neuronales (NHITS, TFT) | No ejecutado | Anexo G |

## Ejecución

```bash
python3 avanzado/05_seleccion_por_coste.py [--margen 0.25 --merma 0.10]
python3 avanzado/02_objetivo_agregado.py
python3 avanzado/07_censura_cota.py
python3 avanzado/04_conformal.py
python3 avanzado/01_tuning_optuna.py --pruebas 40      # requiere optuna
python3 avanzado/06_afinidad_sondeo.py --tiendas BOS_1 NYC_1
python3 avanzado/08_arranque_frio.py
python3 avanzado/09_surtido.py --top 100
python3 avanzado/03_deep_learning.py --series 1000     # requiere neuralforecast y torch
```

## Descripción

**5 · Selección por coste.** El coste esperado del *newsvendor* equivale, salvo una constante, a la
pérdida pinball evaluada en el ratio crítico τ* = Cu/(Cu+Co). Se comparan cinco candidatos sobre
la misma ventana ordenados por MAE, WRMSSE y coste, con una tabla de sensibilidad al margen y a la
merma.

**2 · Objetivo agregado.** La política necesita el total de los nueve días del ciclo, no cada día.
Se entrena un modelo directamente sobre ese total (LightGBM, XGBoost y su ensamble).

**7 · Demanda censurada.** `fact_ventas` registra unidades vendidas, no demandadas; un cero por
rotura es indistinguible de un día sin demanda. Los ceros se separan por verosimilitud y se
construyen dos cotas. La validación compara la longitud de las rachas de ceros con la esperable por
azar: una rotura dura días y el ruido de Poisson no.

**4 · Predicción conforme.** Calibra el cuantil sobre una ventana y evalúa en otra, con cobertura
por clase XYZ.

**1 · Optuna.** Búsqueda sobre el segundo pliegue y validación en el tercero, que no participa de la
búsqueda.

**6 · Afinidad.** No se dispone de datos de cesta, por lo que solo puede medirse afinidad de
demanda tras residualizar calendario, eventos y tráfico de tienda. La prueba decisiva es el nulo
entre tiendas: parejas de productos que nunca pueden compartir cesta.

**8 · Arranque en frío.** Predice la demanda media de un producto nuevo con sus atributos o con la
referencia de la tienda más parecida (`dim_tienda.tienda_mas_parecida`). La partición es por
producto para evitar fuga de información.

**9 · Surtido.** Combina cinco señales sobre las series de baja rotación, dos de ellas frenos: no se
propone retirar la única referencia de un departamento en una tienda ni una referencia que rota
mejor allí que en el resto de la red.

**3 · Redes neuronales.** En la competición M5, de estructura de datos equivalente, los conjuntos
de árboles superaron a las redes. Se deja dimensionado para sondear la calibración de los cuantiles.

## Descartado

- *Más ingeniería de variables de precio:* los precios se mueven en el 1,1 % de las semanas y no lo
  hacen al azar (cuaderno 05).
- *Un LightGBM de mayor tamaño:* rendimientos decrecientes; la búsqueda del experimento 1 cubre ese
  espacio.
- *Redes recurrentes genéricas (LSTM, GRU):* superadas por NHITS y TFT.
- *Entrenar con los cinco años completos:* se descartó inicialmente porque `rmean_364` aportaba la
  referencia anual, pero el cuaderno 03 mostró que 400 días mejoran diciembre un 5,7 %. El modelo
  final usa 400 días; queda sin probar si los cinco años aportan más.
