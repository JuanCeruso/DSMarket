# DSMarket — Lakehouse

> **¿Buscás entender esto para defenderlo, no para programarlo?** Hay una explicación
> pedagógica paso a paso —qué es cada pieza, por qué se eligió, y las preguntas que puede
> hacer el tribunal— publicada como página aparte. Está en la galería de artefactos de
> Claude con el título *El Lakehouse de DSMarket*. Este README es la referencia técnica.

Arquitectura medallón sobre ficheros Parquet, con DuckDB como motor de consulta.

## Por qué así

**El almacén son los ficheros Parquet, no una base de datos.** DuckDB se levanta, registra
las vistas, consulta y se apaga: no guarda estado propio. Es la misma separación
almacenamiento/cómputo que usan Fabric (OneLake), BigQuery o Snowflake, y tiene una
consecuencia concreta: migrar a la nube es cambiar el motor y la ruta de los ficheros,
no reescribir los datos ni las transformaciones. El SQL de `pipeline.py` corre sin cambios
sobre cualquiera de esos tres.

**Compresión conseguida:** 490,9 MB de CSV → 22,1 MB en bronze (mismos datos, formato
columnar comprimido). El grano atómico completo de ventas (58,3 millones de filas) ocupa
83 MB.

## Capas

| Capa | Qué contiene | Regla |
|---|---|---|
| `bronze/` | Copia fiel de las tres fuentes, sin transformar | Nunca se modifica: es la trazabilidad |
| `silver/` | Datos limpios, tipados y en formato largo | Aquí viven las reglas de negocio del EDA |
| `gold/` | Modelo dimensional en estrella + marts | Lo que consumen BI, la API y los modelos |

### Reglas de negocio codificadas en silver

1. **Alineado de precios.** El fichero de precios empieza 5 semanas antes que el de ventas
   (hallazgo de la Tarea 3). El desfase se calcula anclando el rango de semanas al final,
   no al principio. Control de calidad automático: `ventas > 0 sin precio` debe dar **0**.
2. **Eventos derivados por regla de fecha.** Christmas (25/12) y Labor Day (primer lunes de
   septiembre) no vienen en el calendario original y se añaden. Black Friday se evaluó y se
   descartó por no mostrar patrón.
3. **Días de cierre.** Solo Navidad se marca con `es_dia_cierre`, porque la tienda no abre y ningún
   modelo debería intentar predecir ventas ese día. Thanksgiving no cierra (vende un 28 % menos que un
   jueves normal) y no se marca.

## Tablas de gold

| Tabla | Grano | Filas |
|---|---|---|
| `dim_calendario` | día | 1.913 |
| `dim_producto` | producto, con su grupo de la Tarea 2 (`grupo_producto` y su nombre en `arquetipo`) | 3.049 |
| `dim_tienda` | tienda, con la tienda más parecida de la Tarea 2 | 10 |
| `dim_serie` | producto × tienda (con clase ABC/XYZ) | 30.490 |
| `fact_ventas` | producto × tienda × día, valorizado | 58.327.370 |
| `fact_predicciones` | producto × tienda × día futuro (media y p90) | 853.720 |
| `fact_reposicion` | producto × tienda × revisión (nivel objetivo y stock de seguridad) | 121.960 |
| `mart_ventas_dia` | día × tienda × departamento | 133.910 |
| `mart_producto_tienda` | producto × tienda, agregados | 30.490 |

Las dos tablas `fact_predicciones` y `fact_reposicion` son el **ciclo de retroalimentación**:
las salidas de los modelos vuelven al warehouse, así que el dashboard, la API y la app leen
todos de la misma fuente en vez de ficheros sueltos.

## Uso

```bash
python3 scripts/pipeline.py all           # bronze + silver + gold
python3 scripts/carga_predicciones.py     # carga las salidas de los modelos a gold
python3 scripts/carga_clusters.py         # análisis de grupos de producto (Tarea 2): fichas, índices y mejores días
python3 scripts/carga_precios.py          # marts de precios (página «Precios» del panel)
python3 scripts/carga_similitud.py        # perfil y distancia entre tiendas (página «Similitud de tiendas»)
python3 scripts/exportar_powerbi.py       # gold -> gold_csv, los CSV que importa Power BI
```

El orden importa: `exportar_powerbi.py` va siempre el último, porque es el único camino de `gold/` a
`gold_csv/`. Si se ejecuta antes que una carga, el panel se alimenta de una copia vieja del almacén.

```python
from scripts.pipeline import conectar
con = conectar()                          # registra todas las vistas automáticamente
con.execute("SELECT * FROM dim_serie WHERE clase_abc = 'A'").df()
```

## Cuidado con el fan-out

`fact_ventas` (grano diario) y `fact_reposicion` (grano semanal) tienen granos distintos:
unirlas directamente multiplica las métricas de la segunda por el número de días de la
primera. Hay que agregar cada hecho por separado y unir después:

```sql
WITH ventas AS (
    SELECT store_code, item, sum(importe) AS facturacion
    FROM fact_ventas WHERE fecha > DATE '2016-01-25' GROUP BY 1,2
),
repo AS (
    SELECT store_code, item, sum(demanda_esperada) AS demanda, sum(stock_seguridad) AS seguridad
    FROM fact_reposicion WHERE fecha_revision = DATE '2016-04-25' GROUP BY 1,2
)
SELECT t.ciudad, p.arquetipo, round(sum(v.facturacion)) AS facturacion_90d,
       round(sum(r.demanda)) AS demanda_prevista_9d, sum(r.seguridad) AS stock_seguridad
FROM ventas v JOIN repo r USING (store_code, item)
JOIN dim_tienda t USING (store_code) JOIN dim_producto p USING (item)
GROUP BY 1,2 ORDER BY 1, 3 DESC;
```

## Conexión desde PowerBI

El panel (`dashboard/`) importa los **CSV de `gold_csv/`** mediante el parámetro `RutaGold`; no lee
Parquet. Los CSV se generan siempre con `scripts/exportar_powerbi.py`. `fact_ventas` (58 millones de
filas) no se exporta: el panel solo necesita los `mart_*` y las `dim_*`. `fact_predicciones` se parte
en cuatro ficheros, uno por semana, por el límite de tamaño de Power BI.

Si se prefiere leer Parquet de forma nativa, *Obtener datos → Parquet* sobre `gold/` también funciona,
con los mismos nombres de tabla.

## Controles de calidad que pasa el almacén

| Control | Resultado |
|---|---|
| Ventas con unidades > 0 y sin precio | 0 |
| Claves duplicadas en `dim_serie`, `dim_producto`, `fact_predicciones` | 0 |
| Series de `fact_ventas` sin fila en `dim_serie` o `dim_producto` | 0 |
| Predicciones con p90 menor que la media | 0 |
| Fechas de predicción ausentes en `dim_calendario` | 0 |
| `mart_ventas_dia` frente a `fact_ventas` (unidades) | coinciden |

Dos puntos que conviene conocer:

- **`dim_serie` calcula ABC/XYZ con los últimos 90 días de datos** (hasta el 24 de abril de 2016), que es
  lo que necesita la reposición en producción. El notebook 04 clasifica con los 90 días anteriores a la
  ventana que simula (hasta el 27 de marzo), por eso sus recuentos difieren algo (AX: 5.494 frente a 5.634).
- **El 20 % de los días de `fact_ventas` no tiene precio**: son los días anteriores a que el producto
  empiece a venderse en esa tienda. Ninguno tiene ventas.
