# DSMarket — Panel de reposición

Interfaz interactiva sobre el lakehouse y los modelos. Es la pieza pensada para **demostrar el
proyecto en vivo**: un tribunal recuerda una demo mucho más que veinte diapositivas.

## Arrancar

```bash
pip install streamlit altair duckdb pandas scipy
cd PROYECTO
streamlit run app/inicio.py
```

Se abre en http://localhost:8501. No necesita que la API esté corriendo: el panel lee el
lakehouse directamente y aplica exactamente la misma política.

## Estilo

La app comparte identidad visual con el dashboard de Power BI (paleta, logotipo, tipografía). El tema está en `.streamlit/config.toml` y el CSS y los colores de los gráficos en `app/estilo.py`.

## Las seis pestañas

| Pestaña | Qué hace |
|---|---|
| **Hoy en la tienda** | Lista de trabajo del día: referencias a pedir ordenadas por lo que cuesta no pedirlas, con la columna «pedido final» editable y confirmación de las decisiones |
| **Reposición** | La herramienta principal: se elige tienda y producto, se consulta el histórico y la previsión con la banda del percentil 90, se introduce el stock actual y se obtiene cuánto pedir y por qué |
| **Explorador del catálogo** | La matriz ABC/XYZ del catálogo y los mayores pedidos sugeridos de la tienda seleccionada |
| **Curva de servicio** | El resultado de la Tarea 4: cuánto cuesta cada punto de nivel de servicio, con un control para mover la merma y ver cómo se desplaza el óptimo |
| **Preguntar** | Consultas en lenguaje natural traducidas a SQL sobre el almacén |
| **Cómo se integra** | La petición y la respuesta JSON equivalentes de la API, y el diagrama del flujo completo |

## La capa de lenguaje natural

Es opcional: **el panel funciona completo sin ella**. Si existe la variable de entorno
`ANTHROPIC_API_KEY`, se activan dos funciones.

```bash
pip install anthropic
export ANTHROPIC_API_KEY="su-clave"
streamlit run app/inicio.py
```

**La regla de diseño que gobierna todo el módulo: el modelo de lenguaje nunca calcula.**
Un LLM que inventa una cifra de stock en un contexto financiero es un pasivo, no una
funcionalidad. De ahí las tres barreras:

1. **El explicador** recibe las cifras ya resueltas por la política y solo las redacta. El
   prompt le prohíbe explícitamente calcular o inventar causas que no estén en los datos.
2. **El consultor genera SQL, no respuestas.** La aritmética la hace DuckDB.
3. **El SQL se valida antes de ejecutarse** (`explicador.validar_sql`): solo una sentencia,
   solo `SELECT`/`WITH`, solo las nueve vistas del gold, y con `LIMIT` forzado. Además se
   muestra siempre al usuario para que pueda auditarlo.

Sin clave configurada, el explicador cae en una versión por reglas que dice lo mismo con
menos naturalidad, y la pestaña de consultas avisa qué falta.

## Estructura

```
app/
  inicio.py       la interfaz (Streamlit)
  datos.py        única puerta al lakehouse; contiene la política de reposición
  explicador.py   capa de lenguaje natural, con sus barreras de seguridad
```

`datos.sugerir()` implementa la misma política que la API y da resultados idénticos — está
verificado: para SUPERMARKET_3_511 en NYC_1 ambos devuelven nivel objetivo 258,29 y pedido 9.
