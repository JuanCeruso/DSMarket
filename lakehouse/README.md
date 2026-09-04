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
3. **Días de cierre.** Navidad y Thanksgiving se marcan con `es_dia_cierre`, porque la tienda
   no abre y ningún modelo debería intentar predecir ventas esos días.

## Tablas de gold

| Tabla | Grano | Filas |
|---|---|---|
| `dim_calendario` | día | 1.913 |
| `dim_producto` | producto (con arquetipo de la Tarea 2) | 3.049 |
| `dim_tienda` | tienda (con grupo de comportamiento) | 10 |
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
```

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

PowerBI lee Parquet de forma nativa: *Obtener datos → Carpeta* apuntando a `gold/`, o
*Parquet* fichero a fichero. Se recomienda cargar los `mart_*` y las `dim_*` (livianos) y
dejar `fact_ventas` en DirectQuery o pre-agregado, porque 58 millones de filas no hacen
falta para la capa ejecutiva.
