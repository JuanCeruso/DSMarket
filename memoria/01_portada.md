
**NUCLIO DIGITAL SCHOOL**

Máster en Data Science & Inteligencia Artificial

# DSMarket: de la venta diaria a la decisión de reposición

### Previsión de demanda, segmentación e inventario en una cadena de distribución minorista

**Trabajo de Fin de Máster**

Autores

[Nombre y apellidos] · [Nombre y apellidos]
[Nombre y apellidos] · [Nombre y apellidos]

Tutor o tutora

[Nombre y apellidos]

Barcelona, octubre de 2026



---


## Resumen


Este trabajo desarrolla un sistema analítico completo sobre el histórico de ventas de DSMarket,
una cadena de distribución minorista con diez establecimientos en tres ciudades y un catálogo de
3.049 referencias, y lo lleva desde el fichero en bruto hasta la cantidad que debe pedirse de
cada producto en cada tienda. A partir de 58.327.370 observaciones diarias correspondientes a
30.490 series producto-tienda entre 2011 y 2016, se caracteriza la estructura de la demanda, se
segmentan catálogo y red, se comparan familias de modelos de previsión bajo validación temporal
por avance y se simula una política de reposición derivada de la teoría del *newsvendor*.

Los resultados principales son los siguientes. La demanda no es homogénea: solo cinco de los
quince productos más vendidos son comunes a las tres ciudades, y el parecido entre tiendas no
coincide con las fronteras geográficas. El mejor modelo de previsión alcanza un
WRMSSE de 1,0422 (1,0002 en la última ventana con el modelo final de 400 días de historia), y la estrategia de horizonte resulta unas tres veces más influyente que la
elección de biblioteca; reformular el objetivo como el total del ciclo de reposición reduce el
error un 15,7% adicional y elimina un sesgo del −7,4%. Sumar las predicciones individuales
mejora a modelar cada agregado por separado (Prophet, SARIMA) en los cuatro niveles evaluados. La política
de reposición propuesta eleva el nivel de servicio del 86,6% al 96,2% con una reducción del
coste total del 62,5%, y la comparación de candidatos por coste revela que el nivel de servicio
uniforme del 90% resultaba 2,45 veces más caro que el óptimo. La elasticidad precio, en cambio,
no resulta identificable con estos datos: una prueba de falsación temporal desmiente la
estimación obtenida.

**Palabras clave:** previsión de demanda, demanda intermitente, reconciliación jerárquica,
teoría de inventarios, modelo del vendedor de periódicos, arquitectura de datos analíticos.


---


## Abstract

This work develops a complete analytical system on the sales history of DSMarket, a retail chain with ten stores in three cities and a catalogue of 3,049 products, taking it from the raw files to the quantity that should be ordered of each product in each store. Starting from 58,327,370 daily observations of 30,490 product-store series between 2011 and 2016, the structure of demand is characterised, catalogue and store network are segmented, several families of forecasting models are compared under walk-forward temporal validation, and a replenishment policy derived from newsvendor theory is simulated.

Demand is not homogeneous: only five of the fifteen best-selling products are common to the three cities, and the similarity between stores does not follow geographic boundaries. The best forecasting model reaches a WRMSSE of 1.0407 (0.9994 in the last window with the final model, trained on 400 days of history); the horizon strategy proves roughly ten times more influential than the choice of library, and reformulating the target as the total of the replenishment cycle reduces the error by a further 15.7% and removes a bias of −7.4%. Summing individual predictions outperforms modelling each aggregate separately (Prophet, SARIMA) at the four levels evaluated. The proposed replenishment policy raises the service level from 86.6% to 96.2% while reducing total cost by 62.5%, and the cost-based comparison shows that a uniform 90% service level was 2.45 times more expensive than the optimum. Price elasticity, by contrast, is not identifiable with these data: a temporal falsification test refutes the estimate obtained.

**Keywords:** demand forecasting, intermittent demand, hierarchical reconciliation, inventory theory, newsvendor model, analytical data architecture.
