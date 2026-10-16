<!-- =========================================================================
     §1 PORTADA
     Sustituir los campos entre corchetes. Comprobar contra la guía del máster
     si exige logotipo, tipografía o disposición concretos: si los exige, esta
     página se maqueta directamente en Word y no se genera desde aquí.
     ========================================================================= -->

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

<!-- 200-250 palabras. Se escribe AL FINAL, cuando el resto esté cerrado.
     Debe contener: el problema, los datos, los métodos, los tres o cuatro
     resultados numéricos principales y la conclusión. Ni una palabra de
     "se pretende" o "se intentará": el resumen cuenta lo que se hizo. -->

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
WRMSSE de 1,0414 (1,0376 con 400 días de historia), y la estrategia de horizonte resulta unas veinte veces más influyente que la
elección de biblioteca; reformular el objetivo como el total del ciclo de reposición reduce el
error un 15,7% adicional y elimina un sesgo del −7,4%. La reconciliación jerárquica con el
método MinT mejora el error en los seis niveles de agregación, del 15,12% al 13,71%. La política
de reposición propuesta eleva el nivel de servicio del 86,6% al 96,2% con una reducción del
coste total del 62,5%, y la comparación de candidatos por coste revela que el nivel de servicio
uniforme del 90% resultaba 2,45 veces más caro que el óptimo. La elasticidad precio, en cambio,
no resulta identificable con estos datos: una prueba de falsación temporal desmiente la
estimación obtenida.

**Palabras clave:** previsión de demanda, demanda intermitente, reconciliación jerárquica,
teoría de inventarios, modelo del vendedor de periódicos, arquitectura de datos analíticos.


---


## Abstract

<!-- Traducción del resumen. Verificar si el máster exige también versión en inglés. -->

[Traducción del resumen anterior.]


---

