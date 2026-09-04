# 5. Objetivos

## 5.1. Objetivo general

Diseñar y validar un sistema analítico que convierta el histórico de ventas de DSMarket en una
decisión de reposición cuantificada por tienda y producto, evaluando cada etapa con criterios
que puedan reproducirse y, cuando corresponda, refutarse.

La formulación es deliberadamente exigente en dos puntos. Primero, la decisión: el objetivo no
es predecir la demanda sino reponer, y una predicción que no se traduce en unidades pedidas no
cumple el encargo. Segundo, la refutabilidad: cada conclusión del trabajo se acompaña de la
prueba que la habría desmentido si fuera falsa.

## 5.2. Objetivos específicos

**OE1 — Caracterizar la estructura de la demanda.** Describir el comportamiento de las ventas en
las dimensiones temporal, geográfica y de catálogo, cuantificando la heterogeneidad entre
tiendas y ciudades y estableciendo qué eventos del calendario tienen efecto medible sobre la
demanda. Criterio de cumplimiento: disponer de un diagnóstico documentado de calidad de los
datos y de una lista de eventos con su efecto estimado, incluidos los que se descartan.

**OE2 — Segmentar el catálogo y la red de tiendas.** Obtener agrupaciones de productos y de
tiendas basadas en el perfil de demanda, con una elección de número de grupos justificada por
métricas internas y con una comprobación de estabilidad. Criterio de cumplimiento: que la
partición resista una validación *leave-one-out* y que los grupos admitan una interpretación de
negocio, no solamente una separación estadística.

**OE3 — Predecir la demanda a veintiocho días.** Comparar, bajo un mismo protocolo de validación
temporal, familias de modelos de distinta naturaleza —estadísticos clásicos, descomposición
aditiva y aprendizaje automático global— y cuantificar la mejora frente a una referencia
ingenua. Criterio de cumplimiento: una comparación con validación *walk-forward* de tres
pliegues y una métrica de error escalada que permita agregar entre series de escalas distintas.

**OE4 — Responder si los agregados pueden obtenerse sumando.** Determinar si la previsión de los
niveles superiores de la jerarquía (tienda, ciudad, categoría, total) debe calcularse sumando
las previsiones individuales, modelando cada nivel por separado o reconciliando ambas.
Criterio de cumplimiento: una comparación empírica en los seis niveles de la jerarquía y una
garantía de coherencia entre niveles.

**OE5 — Convertir la predicción en una política de reposición.** Formular una política de
inventario derivada de la teoría del *newsvendor*, simularla sobre las 30.490 series con la
demanda real observada y expresar su resultado en unidades monetarias. Criterio de
cumplimiento: una curva de coste frente a nivel de servicio y una recomendación de nivel
objetivo por segmento con su justificación económica.

**OE6 — Evaluar si el precio admite una interpretación causal.** Estimar la elasticidad precio de
la demanda con la especificación habitual en la literatura de paneles y someterla a una prueba
de falsación. Criterio de cumplimiento: o bien una estimación que supere la prueba, o bien la
demostración de que estos datos no permiten identificar el efecto, acompañada del diseño
experimental que sí lo permitiría.

**OE7 — Sostener el sistema en el tiempo.** Sustituir la lectura de ficheros sueltos por un
almacén analítico con una única fuente de verdad, del que se alimenten por igual la
explotación analítica, el servicio de reposición y el cuadro de mando. Criterio de
cumplimiento: reconstrucción íntegra del almacén desde los ficheros de origen mediante un solo
comando, y coincidencia verificable de cifras entre los tres consumidores.

## 5.3. Correspondencia con el encargo

| Petición original | Objetivo | Capítulo de resultados |
|---|---|---|
| «Mirá en profundidad cómo se está vendiendo» | OE1 | §7.1 |
| «Agrupá productos que se comporten parecido» | OE2 | §7.2 |
| Predicción de ventas a cuatro semanas | OE3 | §7.3 |
| «¿Sigue siendo válido sumar las predicciones?» | OE4 | §7.3 |
| Cantidad a reponer por tienda y producto | OE5 | §7.4 |
| Explotar las diferencias de precio | OE6 | §7.5 |
| Migración de fuentes y procesos a la nube | OE7 | §7.6 |
