# Memoria DSMarket

La versión definitiva de la memoria es `Memoria_DSMarket.pdf` (se puede leer directamente en
GitHub). `Memoria_DSMarket.docx` es el mismo documento en Word, del que se exportó el PDF.

## Figuras

Las 30 figuras de la memoria (6.1–6.3 y 7.1–7.27) están en `figuras/`. Se regeneran con:

```bash
python3 figuras/generar_figuras.py --listar      # qué figura produce qué
python3 figuras/generar_figuras.py               # todas
python3 figuras/generar_figuras.py --solo 7.9    # solo algunas
```

Proceden del almacén, de la caché de modelos, de los resultados de `avanzado/resultados/` o de
las salidas de los cuadernos (figuras 7.5 a 7.8 y 7.22), y la 7.26 es una captura de la aplicación.
