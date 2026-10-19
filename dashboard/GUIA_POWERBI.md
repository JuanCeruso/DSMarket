# Guía de construcción del dashboard en PowerBI

Reemplaza el enfoque anterior de `DSMarket_dataset_dashboard.xlsx`. El dashboard ahora se
conecta al **gold del lakehouse**, que es la misma fuente que consumen la API y el panel.
Ventaja concreta: cuando se reentrenan los modelos y se recarga el gold, el dashboard se
actualiza solo. Con el Excel había que regenerarlo a mano.

---

## 1. Conectar

PowerBI lee Parquet de forma nativa. Para que el informe sea portable entre las cuatro
máquinas del equipo, definí primero un **parámetro** con la ruta.

**Inicio → Transformar datos → Administrar parámetros → Nuevo**

| Campo | Valor |
|---|---|
| Nombre | `RutaGold` |
| Tipo | Texto |
| Valor actual | `C:\...\PROYECTO\lakehouse\gold` (la ruta de cada uno) |

Después, para cada tabla: **Inicio → Consulta nueva → Consulta en blanco → Editor avanzado**,
y pegar esto cambiando solo el nombre del fichero:

```m
let
    Origen = Parquet.Document(File.Contents(RutaGold & "\dim_producto.parquet"))
in
    Origen
```

Cada quien cambia `RutaGold` una vez y el informe funciona sin tocar nada más.

### Qué cargar y qué no

| Tabla | Filas | ¿Cargar? |
|---|---|---|
| `dim_calendario` | 1.941 | Sí |
| `dim_producto` | 3.049 | Sí |
| `dim_tienda` | 10 | Sí |
| `dim_serie` | 30.490 | Sí |
| `mart_ventas_dia` | 133.910 | Sí — es la tabla de hechos principal del informe |
| `mart_producto_tienda` | 30.490 | Sí — para los rankings de producto |
| `fact_predicciones` | 853.720 | Sí |
| `fact_reposicion` | 121.960 | Sí |
| `fact_ventas` | **58.327.370** | **No.** Solo si hace falta el grano diario por producto, y en ese caso en DirectQuery |

El total cargado son unas 1,1 millones de filas: el informe abre en segundos. Cargar
`fact_ventas` completo lo haría inmanejable sin aportar nada a la capa ejecutiva — para eso
están los marts, que ya vienen agregados desde el pipeline.

---

## 2. Modelo de datos

Marcá `dim_calendario` como tabla de fechas: **Modelado → Marcar como tabla de fechas →
`fecha`**. Sin eso, la inteligencia de tiempo (comparaciones interanuales) no funciona.

Relaciones, todas **de uno a varios** y en **dirección simple** (de la dimensión al hecho):

```
                        dim_calendario[fecha]
                          │        │        │
              ┌───────────┘        │        └────────────┐
              ▼                    ▼                     ▼
   mart_ventas_dia[fecha]  fact_predicciones[fecha]  fact_reposicion[fecha_revision]
              ▲                    ▲                     ▲
              │                    │                     │
   dim_tienda[store_code]     dim_serie[serie_id] ───────┘
              │                    ▲
              │                    │
              └──── dim_producto[item] ──── mart_producto_tienda[item]
```

Concretamente:

| Desde | Hacia | Cardinalidad |
|---|---|---|
| `dim_calendario[fecha]` | `mart_ventas_dia[fecha]` | 1 : * |
| `dim_calendario[fecha]` | `fact_predicciones[fecha]` | 1 : * |
| `dim_calendario[fecha]` | `fact_reposicion[fecha_revision]` | 1 : * |
| `dim_tienda[store_code]` | `mart_ventas_dia[store_code]` | 1 : * |
| `dim_serie[serie_id]` | `fact_predicciones[serie_id]` | 1 : * |
| `dim_serie[serie_id]` | `fact_reposicion[serie_id]` | 1 : * |
| `dim_serie[serie_id]` | `mart_producto_tienda[serie_id]` | 1 : 1 |
| `dim_producto[item]` | `dim_serie[item]` | 1 : * |
| `dim_tienda[store_code]` | `dim_serie[store_code]` | 1 : * |

`serie_id` (que es `item|store_code`) existe justamente porque PowerBI no admite relaciones
por clave compuesta. Se añadió al gold para esto.

### Dos trampas que conviene evitar

**El fan-out entre granos distintos.** `mart_ventas_dia` es diaria y `fact_reposicion` semanal.
Si se ponen métricas de las dos en el mismo visual sin cuidado, las de reposición se
multiplican por el número de días. Solución: usar medidas separadas y no mezclarlas en la
misma tabla, o filtrar la reposición por una fecha de revisión concreta.

**Las fechas futuras.** `dim_calendario` incluye los 28 días del horizonte de predicción, con
la columna `es_futuro`. En los visuales de ventas reales hay que filtrar `es_futuro = FALSE`,
o aparecerán 28 días con importe cero al final de la serie.

---

## 3. Medidas DAX

Creá una tabla vacía llamada `_Medidas` (**Inicio → Escribir datos**, tabla sin columnas) y
metelas todas ahí. Mantiene el panel de campos ordenado.

```dax
-- ============ VENTAS ============
Unidades vendidas = SUM ( mart_ventas_dia[unidades] )

Facturación = SUM ( mart_ventas_dia[importe] )

Precio medio = DIVIDE ( [Facturación], [Unidades vendidas] )

Unidades año anterior =
CALCULATE ( [Unidades vendidas], SAMEPERIODLASTYEAR ( dim_calendario[fecha] ) )

Variación interanual % =
DIVIDE ( [Unidades vendidas] - [Unidades año anterior], [Unidades año anterior] )

Unidades período anterior =
CALCULATE ( [Unidades vendidas], DATEADD ( dim_calendario[fecha], -1, MONTH ) )

Variación vs período anterior % =
DIVIDE ( [Unidades vendidas] - [Unidades período anterior], [Unidades período anterior] )

Ciudad líder =
CALCULATE (
    FIRSTNONBLANK ( dim_tienda[ciudad], 1 ),
    TOPN ( 1, ALL ( dim_tienda[ciudad] ), [Unidades vendidas], DESC )
)

Tiendas activas = DISTINCTCOUNT ( mart_ventas_dia[store_code] )

-- ============ PREDICCIÓN ============
Demanda prevista = SUM ( fact_predicciones[prediccion_media] )

Demanda prevista p90 = SUM ( fact_predicciones[prediccion_p90] )

Margen de incertidumbre = [Demanda prevista p90] - [Demanda prevista]

Incertidumbre % = DIVIDE ( [Margen de incertidumbre], [Demanda prevista] )

-- ============ REPOSICIÓN ============
Nivel objetivo = SUM ( fact_reposicion[nivel_objetivo] )

Stock de seguridad = SUM ( fact_reposicion[stock_seguridad] )

Demanda esperada del ciclo = SUM ( fact_reposicion[demanda_esperada] )

Nivel de servicio medio =
AVERAGEX ( fact_reposicion, fact_reposicion[nivel_servicio] )

Series que usan el modelo =
CALCULATE (
    DISTINCTCOUNT ( fact_reposicion[serie_id] ),
    fact_reposicion[metodo] = "modelo_cuantilico"
)

-- ============ SEGMENTACIÓN ============
Series = DISTINCTCOUNT ( dim_serie[serie_id] )

Facturación 90 días = SUM ( dim_serie[facturacion_90d] )

% de la facturación =
DIVIDE ( [Facturación 90 días], CALCULATE ( [Facturación 90 días], ALL ( dim_serie ) ) )

% del catálogo =
DIVIDE ( [Series], CALCULATE ( [Series], ALL ( dim_serie ) ) )
```

---

## 4. Las páginas

Las cuatro primeras siguen el wireframe de `dashboard_wireframe.md` (Tarea 1). Las dos
últimas son nuevas: existen porque ahora tenemos predicciones en el modelo.

**Filtros globales** (panel lateral en todas las páginas): ciudad, tienda, rango de fechas,
departamento o categoría. Sincronizalos entre páginas con **Ver → Sincronizar segmentaciones**.

### Página 1 · Resumen ejecutivo
Lo primero que ve Paul o Michelle.
- Cuatro tarjetas: `Unidades vendidas`, `Tiendas activas`, `Variación vs período anterior %`, `Ciudad líder`.
- Gráfico de líneas: `Unidades vendidas` por `dim_calendario[fecha]`, con `dim_tienda[ciudad]` en la leyenda. **Filtrar `es_futuro = FALSE`.**
- Barras: participación de cada ciudad en el período filtrado.

### Página 2 · Comparativa de ciudades y tiendas
Responde el pedido de Michelle sobre si los productos populares varían entre tiendas.
- Barras horizontales: top 10 productos por `Unidades vendidas`, desde `mart_producto_tienda`, con segmentación de ciudad y tienda.
- Barras agrupadas o 100% apiladas: mix de departamento por ciudad.
- Anotación destacando el hallazgo del EDA: **Filadelfia es la ciudad más heterogénea entre sus propias tiendas** (solo 4 de 15 productos top en común, frente a 10 de 15 en Boston).

### Página 3 · Precios entre tiendas
- Barras o diagrama de caja: `Precio medio` por ciudad. El hallazgo es que son casi iguales (medianas de 4,18 a 4,23 USD).
- Tabla: top 15 de productos con mayor dispersión de precio entre tiendas, desde `mart_producto_tienda`.
- Anotación con el hallazgo contraintuitivo: **SUPERMARKET es la categoría con más dispersión de precio** (2,75% de mediana), por encima de ACCESORIES (1,18%).

### Página 4 · Estacionalidad y eventos
- Barras: `Unidades vendidas` promedio por `dim_calendario[evento]` frente al día normal.
- Barras: promedio por día de la semana y por mes.
- Nota: Christmas y Thanksgiving aparecen con ventas casi nulas porque **la tienda cierra** — la columna `es_dia_cierre` los marca. Black Friday se evaluó y se descartó por no mostrar ningún patrón.

### Página 5 · Previsión de demanda *(nueva)*
- Líneas: `Unidades vendidas` histórico y `Demanda prevista` en el horizonte, con banda hasta `Demanda prevista p90`. Es el visual que muestra que hay un modelo detrás.
- Tarjetas: `Demanda prevista` e `Incertidumbre %` del período.
- Tabla por tienda: demanda prevista frente a la media histórica.

### Página 6 · Reposición sugerida *(nueva)*
- Matriz ABC × XYZ con `Series` y `% de la facturación`. Destaca que **AX es el 18% del catálogo y el 56% de la facturación**.
- Tarjetas: `Nivel objetivo` y `Stock de seguridad` totales del próximo ciclo.
- Tabla: productos con mayor pedido sugerido, con `segmento`, `metodo` y `nivel_servicio`.
- Anotación: el nivel de servicio no es una decisión del modelo sino del negocio, y **depende de la merma** (ver Tarea 4).

---

## 5. Antes de dar por cerrado el informe

- [ ] `dim_calendario` marcada como tabla de fechas.
- [ ] Todas las relaciones en dirección simple (ninguna bidireccional: generan ambigüedad).
- [ ] Los visuales de ventas reales filtran `es_futuro = FALSE`.
- [ ] Tema de color personalizado con la paleta de marca: `#2a78d6` (azul principal), `#6a9f1f` (verde), `#eda100` (dorado), `#0a2a5c` (texto). **Ver → Temas → Personalizar tema.**
- [ ] Ningún visual mezcla métricas de `mart_ventas_dia` con métricas de `fact_reposicion` sin filtrar por una fecha de revisión.
- [ ] El informe abre en menos de 10 segundos con los datos actualizados.

## 6. Para actualizar los datos

```bash
python3 lakehouse/scripts/pipeline.py all          # reconstruye bronze, silver y gold
python3 lakehouse/scripts/carga_predicciones.py    # vuelca las predicciones al gold
python3 lakehouse/scripts/carga_clusters.py        # grupos de producto (Tarea 2)
python3 lakehouse/scripts/carga_precios.py         # marts de precios
python3 lakehouse/scripts/exportar_powerbi.py      # gold -> gold_csv (lo que importa PowerBI); siempre el último
```

Después, en PowerBI: **Inicio → Actualizar**. Los CSV de `gold_csv/` se sobrescriben en el
mismo sitio, así que no hay que reconfigurar nada.

## Campana de estimación (página nueva)

Página «Campana de estimación», accesible desde el botón de la página «Colchón de seguridad». Muestra la distribución normal de la demanda de la cobertura (9 días) y sombrea la parte que cubre el nivel de confianza elegido en el desplegable.

- Tablas auxiliares: `param_confianza` (niveles del 50 % al 99 %) y `eje_campana` (eje z de −4 a 4).
- Medidas (carpeta `_Medidas`, prefijo «Campana:»): demanda esperada, desviación típica equivalente (stock de seguridad / z del nivel de servicio vigente, sumada entre series), densidad, zona cubierta, nivel objetivo, stock de seguridad y riesgo de rotura.
- Con un producto y una tienda seleccionados es la campana exacta de esa serie; con varias series la σ es la suma de las σ de cada serie, coherente con que el colchón se fija serie a serie.
- Es una aproximación normal: para las series X el nivel real se obtiene del percentil empírico, por lo que la σ equivalente es solo una referencia visual.
