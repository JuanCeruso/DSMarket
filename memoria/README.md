# Memoria DSMarket — borrador

Un fichero por sección. **Editad los `.md`, no el `.docx`**: el Word se regenera desde ellos con
un comando y así no hay dos versiones que puedan divergir.

```bash
cat _meta.md 01_portada.md 02_indice.md 03_introduccion.md 04_justificacion.md 05_objetivos.md \
    06_metodologia.md 07_1_tiendas.md 07_2_clustering.md 07_3_forecasting.md \
    07_4_abastecimiento.md 07_5_elasticidad.md 07_6_ingenieria.md 07_7_mlops.md \
    07_8_conclusiones.md 08_referencias.md 09_anexos.md > _completa.md
pandoc _completa.md -o Memoria_DSMarket_borrador.docx --toc --toc-depth=3 \
       --from=markdown+tex_math_dollars
```

> **Las fórmulas solo se ven en Word.** Van embebidas como OMML, que es el formato nativo de
> Word. Si convertís el `.docx` a PDF con LibreOffice desaparecen sin avisar: exportad el PDF
> desde Word.

## Estado

| Sección | Fichero | Estado |
|---|---|---|
| §1 Portada y resumen | `01_portada.md` | Plantilla con el resumen redactado · faltan nombres y el *abstract* |
| §2 Índice | `02_indice.md` | Instrucciones · se genera automático |
| §3 Introducción | `03_introduccion.md` | Redactada |
| §4 Justificación y estado del arte | `04_justificacion.md` | Redactada · 31 referencias APA |
| §5 Objetivos | `05_objetivos.md` | Redactada |
| §6 Metodología | `06_metodologia.md` | Redactada · 3 figuras marcadas |
| §7.1 Tiendas | `07_1_tiendas.md` | Redactada · 4 figuras marcadas |
| §7.2 Comportamiento | `07_2_clustering.md` | Redactada · 5 figuras marcadas |
| §7.3 Predicción | `07_3_forecasting.md` | Redactada · 6 figuras marcadas |
| §7.4 Reposición | `07_4_abastecimiento.md` | Redactada · 3 figuras marcadas · + §7.4.7 demanda censurada |
| §7.5 Precio | `07_5_elasticidad.md` | Redactada · 3 figuras marcadas |
| §7.6 Ingeniería | `07_6_ingenieria.md` | Redactada · 2 figuras marcadas · + capa de operación y plan de despliegue |
| §7.7 MLOps | `07_7_mlops.md` | Redactada · 1 figura marcada · trazabilidad, puerta, pruebas, lazo, entorno |
| §7.8 Conclusiones | `07_8_conclusiones.md` | Redactada · renumerada desde §7.7 |
| §8 Referencias | `08_referencias.md` | Redactada · verificar las 4 marcadas con `[v]` |
| §9 Anexos | `09_anexos.md` | Estructura de siete anexos · falta el contenido de cada uno |

Extensión actual: unas 24.000 palabras, **53 páginas sin figuras**. Con las 28 figuras y los
anexos queda holgadamente por encima de las 62 previstas; si hay que recortar, el sitio natural
es §4, que es la sección más larga y la menos propia.

## Lo que falta

**Las 28 figuras.** Están marcadas en el texto con `[FIGURA n.m]`, cada una con su título y la
indicación de qué cuaderno la produce. Buscad `FIGURA` en los `.md` para localizarlas todas.

Veintiséis se generan solas y quedan en `memoria/figuras/`:

```bash
python3 figuras/generar_figuras.py --listar
python3 figuras/generar_figuras.py               # todas
python3 figuras/generar_figuras.py --solo 7.9 7.14
```

Las dos que no: la **7.19** (elasticidad por arquetipo), que no está cacheada y hay que exportar
del cuaderno, y la **7.23** (pantallas del panel), que son capturas de la aplicación en marcha a
200 ppp.

**Cuatro referencias por verificar.** Las marcadas `[v]` en `08_referencias.md`: volumen, número
y páginas contra la fuente. Y añadir DOI a todas las que lo tengan.

**Los nombres y el abstract** en `01_portada.md`. El resumen en castellano ya está escrito.

**El contenido de los anexos.** La estructura está; falta adjuntar o referenciar cada pieza.

## Reglas de forma ya cerradas

- Registro académico: tercera persona, pasado, sin apelaciones al lector. Los notebooks conservan
  su voz de negocio; la memoria tiene la suya. No hacen falta dos versiones del cuaderno de EDA.
- Cada cifra aparece **una sola vez** con su intervalo o su significación, y después se
  referencia. Nada de repetir «WRMSSE 1,0414» en cinco sitios con distintos decimales.
- Los anexos se referencian desde el cuerpo o no van.

## Secciones que pueden crecer según lo que se ejecute

| Si se ejecuta | Qué sección cambia |
|---|---|
| `avanzado/05_seleccion_por_coste.py` | §7.4.5 pasa de propuesta a resultado, y probablemente merezca capítulo propio |
| `avanzado/06_afinidad_sondeo.py` | Sección nueva en §7.2 si hay señal; párrafo en §7.8.4 si no |
| `avanzado/02_objetivo_agregado.py` | §7.3.3 y el trabajo futuro de §7.8.4 |
| `avanzado/04_conformal.py` | §7.3.6 gana una garantía formal de cobertura |
| `avanzado/07_censura_cota.py` | §7.4.7 pasa de método descrito a cotas con cifras |
| `avanzado/08_arranque_frio.py` | Sección nueva en §7.3 o §7.6, y el trabajo futuro se acorta |
| `avanzado/09_surtido.py` | Sección nueva en §7.2, como cierre de la matriz ABC/XYZ |
