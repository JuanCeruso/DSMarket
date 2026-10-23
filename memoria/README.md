# Memoria DSMarket

Un fichero por sección. Los `.md` son la fuente: el documento Word se regenera desde ellos con un
comando, de modo que no existen dos versiones que puedan divergir.

```bash
cd memoria
cat _meta.md 01_portada.md 02_indice.md 03_introduccion.md 04_justificacion.md 05_objetivos.md \
    06_metodologia.md 07_1_tiendas.md 07_2_clustering.md 07_3_forecasting.md \
    07_4_abastecimiento.md 07_5_elasticidad.md 07_6_ingenieria.md 07_7_mlops.md \
    07_8_conclusiones.md 08_referencias.md 09_anexos.md > _completa.md
pandoc _completa.md -o Memoria_DSMarket.docx --toc --toc-depth=3 \
       --from=markdown+tex_math_dollars
```

Las fórmulas se incrustan en formato OMML, nativo de Word. Si el `.docx` se convierte a PDF con
LibreOffice desaparecen sin aviso; el PDF debe exportarse desde Word.

## Figuras

Las 30 figuras (6.1–6.3 y 7.1–7.27) están incrustadas desde `figuras/`. Se regeneran con:

```bash
python3 figuras/generar_figuras.py --listar      # qué figura produce qué
python3 figuras/generar_figuras.py               # todas
python3 figuras/generar_figuras.py --solo 7.9    # solo algunas
```

Proceden del almacén, de la caché de modelos, de los resultados de `avanzado/resultados/` o de
las salidas de los cuadernos (figuras 7.5 a 7.8 y 7.22), y la 7.26 es una captura de la aplicación.

## Pendiente de completar por los autores

Nombres de autores y tutor en la portada.
