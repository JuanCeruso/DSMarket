# Guía para montar la presentación de defensa

Documento de trabajo: cómo se armaría la presentación, diapositiva a diapositiva, integrando los
comentarios de Raquel y las páginas del cuadro de mando. Complementa a `guion.md` (reparto y tiempos).

## Principios de montaje

1. **Una diapositiva, una idea, una cifra.** El título es la conclusión («Solo 5 de los 15 productos
   más vendidos son comunes a las tres ciudades»), no el tema («Solapamiento por ciudad»).
2. **El cuadro de mando es la prueba, no el relleno.** Cada captura se recorta a un solo gráfico,
   con el filtro visible, y se acompaña de la página de Power BI de la que procede.
3. **Orden de cada bloque:** pregunta → resultado → qué decisión cambia.
4. **Todo número de la diapositiva debe poder rastrearse** a un cuaderno o a una tabla del oro; el pie
   indica la fuente («Fuente: tabla `mart_ventas_dia`, 2011–2016»).

## Comentarios de Raquel: dónde se resuelve cada uno

| Diap. | Comentario | Qué cambiar | Pieza de apoyo |
|---|---|---|---|
| 01 | Aclarar el origen de los datos | Añadir una línea bajo la cifra de apertura: «Datos de ventas diarias de una cadena minorista de EE. UU. (10 tiendas, 3 ciudades, 3.049 productos, 2011–2016), tomados del conjunto público M5 Forecasting; no son datos de una empresa real». Mostrar un mini esquema fuente → bronce/plata/oro | Página *Resumen* (alcance de los datos) |
| 03 | Aclarar el «5 de 15» | Reescribir como «De los 15 productos más vendidos de cada ciudad, solo 5 aparecen en las tres». Dibujar tres columnas de 15 puntos con los 5 comunes resaltados. Añadir la lectura: «el resto del top es propio de cada ciudad» | Página *Ciudades y tiendas* |
| 05 | Renombrar los clústeres | Usar siempre los nombres de negocio y nunca «clúster 0…5»: Alta rotación diaria, Pico de fin de semana, Pico de diciembre, Venta esporádica con picos en eventos, etc. (los de `dim_arquetipo`). Tabla de seis filas: nombre, % del catálogo, % de la facturación, rasgo distintivo | Página *Grupos de producto* |
| 06 | Cambiar la presentación del parecido entre tiendas y su título | Título: **«Parecido de tiendas: ¿se comportan igual las que están en la misma ciudad?»**. Sustituir el dendrograma/mapa por la matriz de distancias de 10×10 y el perfil por variable (misma vista que la página del cuadro de mando) | Página *Parecido de tiendas* |
| 07 | Mostrar de dónde sale el 5 % | Descomponer el 5 % en una cascada o en tres barras: qué parte viene de cada fuente (p. ej. mejor pronóstico, colchón ajustado por rotación, nivel de servicio). La cifra sola no se sostiene | Página *Colchón de seguridad* y *Campana de estimación* |
| 08 | «Unos 96 de cada 100» → «un 96 % de» | Sustituir en diapositiva y guion; revisar el resto de la presentación en busca de fórmulas del tipo «x de cada 100» | — |

> Nota sobre el 07: antes de la defensa hay que fijar con exactitud qué es «el 5 %» (ahorro de coste,
> mejora de WAPE, reducción de roturas…). La descomposición debe sumar el total; si no suma, se
> indica el residuo como «efecto no atribuido».

## Estructura propuesta (≈ 17 diapositivas, 18 min + 2 de reserva)

### Bloque A · El caso (4 min)
1. **La cifra de apertura.** «161.000 $ de margen perdidos cada cuatro semanas por producto ausente
   frente a 11.000 $ por inventario inmovilizado». Origen de los datos al pie (comentario 01).
2. **El encargo.** 10 tiendas · 3 ciudades · 3.049 productos · 5 años · 58 M de filas.
3. **La cadena de preguntas.** Cuatro peticiones encadenadas; la última (cuántas unidades pedir) es
   la única que mueve dinero.

### Bloque B · Qué pasa en las tiendas (4 min)
4. **Cinco de quince.** Solapamiento del top 15 por ciudad (comentario 03). *Dashboard: Ciudades y tiendas.*
5. **Seis grupos de producto**, con nombre de negocio (comentario 05). *Dashboard: Grupos de producto.*
6. **Parecido de tiendas** (comentario 06): por qué no se agrupan con un algoritmo (más variables
   que tiendas) y qué muestra la comparación directa: el perfil no coincide con la ciudad.
   *Dashboard: Parecido de tiendas.*
7. **La matriz ABC/XYZ** en diez segundos: AX = 56 % de la facturación; CZ = 28 % del catálogo
   para el 3,5 %.

### Bloque C · Predecir y decidir (6 min)
8. **El resultado incómodo.** Nada ganaba a la media móvil de 28 días; el problema estaba mal
   planteado. Estrategia por bloques semanales: WRMSSE 1,0407.
9. **Comparación de modelos y medida por semanas** (WAPE semanal del 76 % al 40 %).
10. **Sumar es válido.** Ascendente frente a directo por nivel (5,5 % a 9,9 %).
11. **La refutación.** Cambio de signo por segmento: +26 % en venta esporádica, −7 % en alta
    rotación diaria. *Dashboard: Precisión/Colchón por segmento.*
12. **Dónde está el ahorro** (comentario 07): descomposición del 5 %. *Dashboard: Colchón de seguridad.*
13. **La campana de estimación.** Mover el nivel de confianza y ver cómo crece el colchón: la
    forma más intuitiva de explicar el nivel de servicio. *Dashboard: Campana de estimación.*
14. **La curva de servicio:** el nivel óptimo lo decide la merma, no el margen. Y el placebo del
    precio en una frase (elasticidad −0,395; placebo −0,398).

### Bloque D · Sostenerlo y cerrar (4 min)
15. **El sistema:** bronce → plata → oro; API, panel y Power BI leen las mismas tablas.
16. **Demo en vivo (60–90 s)** con vídeo de reserva.
17. **Las tres refutaciones** (Black Friday, métrica de error frente a la de negocio, elasticidad).

## Cómo usar el cuadro de mando durante la defensa

- Abrir Power BI en la página que corresponda **solo** en las diapositivas 4, 5, 6, 13 como apoyo;
  en el resto, captura estática. Un cambio de ventana por bloque como máximo.
- Preparar un **marcador por diapositiva** (filtros ya puestos) para no manipular filtros en directo.
- Orden de páginas que sigue el relato: Resumen → Ciudades y tiendas → Grupos de producto →
  Parecido de tiendas → Colchón de seguridad → Campana de estimación.
- Plan B: capturas en PNG de las cuatro páginas, a 1920×1080, dentro de la propia presentación.

## Lista de comprobación previa

- [ ] Abrir el PBIP, **actualizar** y revisar las páginas modificadas (Resumen, Ciudades y tiendas,
      Cómo se compra, Parecido de tiendas, Colchón, Campana, Explorador).
- [ ] Todas las cifras de la presentación coinciden con la memoria y con el cuadro de mando.
- [ ] Ningún «clúster N» ni «x de cada 100» en las diapositivas.
- [ ] Definir con exactitud el «5 %» y su descomposición.
- [ ] Ensayo cronometrado con el proyector y la demo.
