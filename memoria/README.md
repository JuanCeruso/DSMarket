# Memoria DSMarket

Un fichero por sección. Los `.md` son la fuente: el documento Word se regenera desde ellos con un
comando, de modo que no existen dos versiones que puedan divergir.

```bash
cd memoria
python generar_word.py
```

El script une los capítulos dejando una línea en blanco entre ellos (sin ella pandoc no reconoce
el título del capítulo siguiente y lo deja como texto) y usa `plantilla.docx`, que pone el número
de página en el pie y empieza cada capítulo en una página nueva. Al abrir el Word hay que aceptar
«actualizar los campos» (o clic derecho en el índice → «Actualizar campo») para que el índice
muestre los números de página.

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
