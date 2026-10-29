# Documentación del proyecto DSMarket

Tres documentos HTML. Se abren con doble clic en cualquier navegador; no
necesitan servidor ni conexión.

| Archivo | Qué es | Cuándo leerlo |
|---|---|---|
| `instructivo.html` | Manual de ejecución de principio a fin: qué correr, en qué orden, tiempos y salidas esperadas, tabla de uso diario y troubleshooting. | Antes de tocar nada, y cada vez que algo falle. |
| `teoria.html` | Los métodos usados en cada etapa y la teoría que los justifica, con las fórmulas explícitas: Jaccard, K-Means, modelos globales, Tweedie, estrategias de horizonte, RMSSE/WRMSSE, pinball loss, reconciliación MinT, newsvendor, Frisch-Waugh-Lovell. | Para entender la base metodológica de cada etapa. |
| `lakehouse.html` | Cómo y dónde se construyó la DuckDB: arquitectura medallion (bronze/silver/gold), esquema estrella, el unpivot, el bucle de realimentación de predicciones y las trampas encontradas. | Para entender la parte de ingeniería de datos. |

