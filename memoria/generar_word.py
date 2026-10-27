"""Genera Memoria_DSMarket.docx a partir de los .md de esta carpeta.

    python generar_word.py

Une los capítulos dejando una línea en blanco entre ellos (sin ella, pandoc no reconoce
el título del capítulo siguiente) y usa plantilla.docx, que añade el número de página en el
pie y empieza cada capítulo en una página nueva. Al abrir el Word, aceptar «actualizar los
campos» para que el índice muestre los números de página; el PDF se exporta desde Word.
"""
import pathlib, subprocess

AQUI = pathlib.Path(__file__).parent
CAPITULOS = ['_meta.md', '01_portada.md', '02_indice.md', '03_introduccion.md', '04_justificacion.md',
             '05_objetivos.md', '06_metodologia.md', '07_1_tiendas.md', '07_2_clustering.md',
             '07_3_forecasting.md', '07_4_abastecimiento.md', '07_5_elasticidad.md',
             '07_6_ingenieria.md', '07_7_mlops.md', '07_8_conclusiones.md', '08_referencias.md',
             '09_anexos.md']

texto = '\n\n'.join((AQUI / c).read_text(encoding='utf-8').strip('\n') for c in CAPITULOS) + '\n'
(AQUI / '_completa.md').write_text(texto, encoding='utf-8')
subprocess.run(['pandoc', '_completa.md', '-o', 'Memoria_DSMarket.docx',
                '--from=markdown+tex_math_dollars', '--reference-doc=plantilla.docx',
                '--resource-path=.'], cwd=AQUI, check=True)
(AQUI / '_completa.md').unlink()
print('Memoria_DSMarket.docx generada')
