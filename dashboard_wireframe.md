# DSMarket — Wireframe del dashboard ejecutivo (Tarea 1)

Preparado por Nicole (Data Science) para PowerBI Desktop. Basado en `DSMarket_dataset_dashboard.xlsx` (ver hoja "Léame" de ese archivo para el detalle de tablas) y en los hallazgos de `01_EDA_DSMarket.ipynb`.

**Filtros globales (panel de filtros en todas las páginas):**
- Ciudad (`dim_tienda.ciudad`)
- Tienda (`dim_tienda.tienda_id`)
- Rango de fechas (`dim_calendario.fecha`)
- Departamento / Categoría (`dim_producto` o directo en `fact_ventas_diarias`)

Paleta: azul de marca `#2a78d6` como color principal, verde `#6a9f1f` y dorado `#eda100` como colores de apoyo para comparar las 3 ciudades (mismo criterio que el notebook de EDA — mantenerlo para que la memoria y el dashboard se vean como una sola pieza).

---

## Página 1 — Resumen ejecutivo (ventas y tendencia)

La portada del dashboard — lo primero que ve Paul o Michelle al abrirlo.

- **KPI cards** (arriba, 4 tarjetas): unidades totales vendidas (período filtrado), cantidad de tiendas activas, variación % vs. período anterior, ciudad líder en ventas.
- **Gráfico de línea principal:** unidades vendidas por día (o por semana, con un selector), una serie por ciudad — el mismo gráfico de la sección 7 del notebook de EDA, con color por ciudad.
- **Gráfico de barras chico:** % de participación de cada ciudad en las ventas totales del período filtrado.

## Página 2 — Comparativa ciudades y tiendas

Responde directamente el pedido de Michelle: *"¿los productos más populares varían entre ciudades o tiendas?"*.

- **Top 10 productos** (gráfico de barras horizontal), con selector de ciudad/tienda para cambiar el foco — usa `fact_ventas_producto` + `dim_producto`.
- **Mix de categoría/departamento por ciudad** (barras agrupadas o 100% apiladas) — usa `fact_ventas_diarias` agregado por departamento.
- **Tabla o matriz de similitud entre tiendas** (opcional, más avanzado): si PowerBI lo permite con una matriz o un visual de terceros, mostrar qué tan parecidas son las tiendas entre sí (el hallazgo de Filadelfia como la más heterogénea es un buen punto para destacar acá con una anotación).

## Página 3 — Precios entre tiendas

Vinculado al pedido de Michelle de explotar diferencias de precio para marketing.

- **Boxplot o barras de precio promedio por ciudad** — usa `fact_precios` + `dim_tienda` (nivel de precio: prácticamente igual entre ciudades, según el EDA).
- **Ranking de productos con mayor dispersión de precio entre tiendas** (tabla, top 15) — usa `fact_precios` agrupado por producto (max-min).
- **Dispersión de precio por categoría** (boxplot o barras de error) — el hallazgo de que SUPERMARKET es la categoría más dispersa (no ACCESORIES) va bien destacado acá con una anotación de texto, porque es contraintuitivo.

## Página 4 — Estacionalidad y eventos

- **Barras: ventas promedio por evento vs. día normal** — usa `dim_calendario.evento` cruzado con ventas diarias totales. Incluye Christmas y Labor Day (agregados por regla de fecha, no venían en el calendario original). Se evaluó agregar Black Friday pero no mostró ningún patrón distinguible frente a un día normal, así que no se incluye como evento del calendario extendido.
- **Barras: ventas promedio por día de la semana.**
- **Barras o línea: ventas promedio por mes del año.**

---

## Notas de implementación en PowerBI

- Todas las tablas del Excel tienen columnas con nombres consistentes (`tienda_id`, `producto_id`, `fecha`) para que PowerBI arme las relaciones automáticamente al importar.
- `fact_ventas_diarias` está a nivel tienda+departamento+día (no por producto individual) — deliberado, para que el modelo sea liviano; si en algún momento hace falta bajar a nivel producto+día, avisame y armo esa tabla aparte (crece a ~58M filas, conviene evaluar si realmente hace falta para la capa ejecutiva).
- Sugerido: un tema de color personalizado en PowerBI con `#2a78d6` / `#6a9f1f` / `#eda100` para que coincida con la paleta del notebook y de la memoria.
