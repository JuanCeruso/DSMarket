# -*- coding: utf-8 -*-
"""Añade al notebook 01 el apartado 11.1 (revisión tras la tutoría): Black Friday y los eventos vistos
por semanas. Solo se ejecutan las celdas nuevas, que son autocontenidas (leen los CSV originales).

    python3 actualizar_eda.py
"""
import sys, copy, nbformat
from nbclient import NotebookClient

CODE_EDA_A = r'''
# Revisión tras la tutoría: Black Friday y los eventos vistos por semanas.
# Celda autocontenida: recalcula el total diario desde el CSV original.
_ventas = pd.read_csv("data_dsmarket/data_dsmarket/item_sales.csv")
_dias = [c for c in _ventas.columns if c.startswith('d_')]
_cal = pd.read_csv("data_dsmarket/data_dsmarket/daily_calendar_with_events.csv", parse_dates=['date'])
total_dia = pd.Series(_ventas[_dias].sum().values, index=_cal.set_index('d').loc[_dias, 'date'].values)
del _ventas

# Black Friday = el día siguiente a Thanksgiving. Se compara con el mismo día de la semana
# (viernes) de las dos semanas anteriores y las dos siguientes.
filas_bf = []
for tg in _cal.loc[_cal['event'] == 'Thanksgiving', 'date']:
    bf = tg + pd.Timedelta(days=1)
    vecinos = [bf + pd.Timedelta(weeks=k) for k in (-2, -1, 1, 2)]
    ref = total_dia.reindex(vecinos).mean()
    filas_bf.append({'año': bf.year, 'Black Friday': total_dia.get(bf), 'viernes de alrededor (media)': ref,
                     'diferencia %': (total_dia.get(bf) / ref - 1) * 100})
tabla_bf = pd.DataFrame(filas_bf).set_index('año')
tabla_bf.loc['media'] = tabla_bf.mean()
tabla_bf.round(1)
'''

CODE_EDA_B = r'''
# Ventas de la semana del evento y de las semanas de alrededor, respecto a las 4 semanas previas.
# Semanas de sábado a viernes, como el calendario original.
semana = (total_dia.index - pd.Timestamp('2011-01-29')).days // 7
total_sem = total_dia.groupby(semana).sum()
eventos = {'Thanksgiving': _cal.loc[_cal['event'] == 'Thanksgiving', 'date'],
           'Navidad': pd.to_datetime([f'{y}-12-25' for y in range(2011, 2016)]),
           'Super Bowl': _cal.loc[_cal['event'] == 'SuperBowl', 'date'],
           'Semana Santa': _cal.loc[_cal['event'] == 'Easter', 'date'],
           'Labor Day': pd.to_datetime([pd.Timestamp(y, 9, 1) + pd.Timedelta(days=(7 - pd.Timestamp(y, 9, 1).weekday()) % 7)
                                        for y in range(2011, 2016)])}
DESPL = [-2, -1, 0, 1]
perfil = {}
for nombre, fechas in eventos.items():
    filas = []
    for f in fechas:
        w = (f - pd.Timestamp('2011-01-29')).days // 7
        base = total_sem.reindex(range(w - 6, w - 2)).mean()
        if np.isnan(base) or w + 1 > total_sem.index.max():
            continue
        filas.append([(total_sem[w + k] / base - 1) * 100 for k in DESPL])
    perfil[nombre] = np.mean(filas, axis=0)
perfil = pd.DataFrame(perfil, index=['2 semanas antes', 'semana anterior', 'semana del evento', 'semana siguiente']).T

fig, ax = plt.subplots(figsize=(10, 4.5))
colores_ev = [DSMARKET_NAVY, DSMARKET_GOLD, DSMARKET_BLUE, DSMARKET_GREEN, '#8a5fd6']
for (nombre, fila), c in zip(perfil.iterrows(), colores_ev):
    ax.plot(perfil.columns, fila.values, marker='o', linewidth=2, color=c, label=nombre)
ax.axhline(0, color='#52514e', linewidth=1)
ax.set_ylabel('% sobre las 4 semanas previas')
ax.set_title('Ventas semanales alrededor de cada evento', color=DSMARKET_NAVY, fontweight='bold')
ax.legend(frameon=False, fontsize=9)
plt.tight_layout(); plt.show()
perfil.round(1)
'''

MD_EDA_TITULO = """
### 11.1. Revisión tras la tutoría: Black Friday y los eventos vistos por semanas

La tutora recomendó medir los festivos **a nivel semanal** y no solo el día exacto, porque las compras de fechas como Black Friday o Navidad se reparten por los días de alrededor. Se revisan dos cosas:

1. **Black Friday**: el texto de arriba decía que no mostraba ningún patrón, pero no había un cálculo que lo respaldara. Se compara cada Black Friday con los viernes de las dos semanas anteriores y las dos siguientes.
2. **Las semanas alrededor de cada evento**: ventas de la semana del evento y de las semanas vecinas (de sábado a viernes, como el calendario original), comparadas con las 4 semanas previas.
"""

MD_EDA_BF = """
**Hallazgo: en estos datos, Black Friday vende un 24 % menos que un viernes normal.**

Los cinco años van en la misma dirección (entre −17 % y −29 %), así que no es ruido. Es lo contrario de lo que se esperaría en una cadena estadounidense, y tiene una explicación probable: Black Friday cae justo después de Thanksgiving, que es día de cierre, y la actividad tarda en recuperarse. El sábado siguiente ya vende por encima de lo normal.

Por eso no se añade Black Friday como evento de pico al calendario extendido: no lo es en estos datos. Pero sí queda recogido en el modelo de la Tarea 3 a través de las variables de evento semanal (días desde el último evento, que aquí es Thanksgiving).
"""

MD_EDA_SEMANAS = """
**Hallazgo: los eventos mueven las ventas de toda la semana, y en Navidad, de las semanas anteriores.**

- **Navidad:** las dos semanas previas venden un **4-5 % más** que el mes anterior, y la semana del 25 cae un 12 % por el día de cierre. Las compras de Navidad se adelantan: mirar solo el día 25 (cuando la tienda está cerrada) pierde el efecto real.
- **Thanksgiving:** la semana del evento y la siguiente venden menos (−7 % y −8 %): el cierre del jueves y un Black Friday flojo.
- **Super Bowl:** la semana del evento y la siguiente venden un 13-16 % más. Parte de esa subida es la recuperación normal tras la cuesta de enero (la referencia son las 4 semanas previas, que caen en enero), pero confirma que el efecto no se queda en el domingo del partido.
- **Semana Santa y Labor Day:** efectos pequeños a nivel semanal (entre +1 % y +5 %), aunque el día en sí tenga un pico.

**Consecuencia para la Tarea 3:** la recomendación de la tutora tiene fundamento en los datos. El modelo de predicción incorpora variables de evento semanal (si la semana tiene un evento y cuántos días faltan o han pasado), y se entrena con más de un año de historia para que vea cada evento al menos una vez (notebook 03, sección 16).
"""

PRE = """import numpy as np, pandas as pd, matplotlib.pyplot as plt, warnings
warnings.filterwarnings('ignore')
DSMARKET_NAVY = "#0a2a5c"; DSMARKET_BLUE = "#2a78d6"; DSMARKET_GOLD = "#eda100"; DSMARKET_GREEN = "#6a9f1f"
%matplotlib inline"""
nb = nbformat.read('01_EDA_DSMarket.ipynb', as_version=4)
c = nb.cells
if any(x.source.startswith('### 11.1.') for x in c):
    raise SystemExit('El apartado 11.1 ya está en el notebook')
assert c[62].source.startswith('**Hallazgo:** hay estacionalidad semanal') and c[63].source.startswith('## 12.')
nuevas = [nbformat.v4.new_markdown_cell(MD_EDA_TITULO.strip()), nbformat.v4.new_code_cell(CODE_EDA_A.strip()),
          nbformat.v4.new_markdown_cell(MD_EDA_BF.strip()), nbformat.v4.new_code_cell(CODE_EDA_B.strip()),
          nbformat.v4.new_markdown_cell(MD_EDA_SEMANAS.strip())]
tmp = nbformat.v4.new_notebook(); tmp.metadata = nb.metadata
tmp.cells = [nbformat.v4.new_code_cell(PRE)] + [copy.deepcopy(x) for x in nuevas]
NotebookClient(tmp, timeout=1800, kernel_name='python3', resources={'metadata': {'path': '.'}}).execute()
nb.cells = c[:63] + tmp.cells[1:] + c[63:]
# textos que afirmaban algo sin respaldo
def rep(a, b):
    n = 0
    for x in nb.cells:
        if a in x.source: x.source = x.source.replace(a, b); n += 1
    assert n == 1, a[:50]
rep("También evaluamos agregar **Black Friday** (día siguiente a Thanksgiving), pero esas 5 fechas no muestran ningún patrón distinguible frente a un día normal, así que no lo tratamos como un evento importante del calendario extendido — sin un equipo de datos real al que consultarle cómo se generó el dataset, no tiene sentido dejarlo como hallazgo abierto.",
    "También evaluamos agregar **Black Friday** (día siguiente a Thanksgiving): en estos datos no es un pico sino al revés, vende un 24 % menos que un viernes normal (apartado 11.1), así que no lo tratamos como evento de pico del calendario extendido.")
rep("Evaluamos Black Friday y no mostró ningún efecto distinguible en estos datos, así que no lo dejamos como evento destacado del calendario (ver nota de la sección anterior).",
    "Black Friday no es un pico en estos datos: vende menos que un viernes normal (apartado 11.1).")
for x in nb.cells:
    if x.cell_type == 'code':
        for o in x.get('outputs', []):
            if o['output_type'] == 'error': raise SystemExit(f"error: {o['evalue']}")
nbformat.write(nb, '01_EDA_DSMarket.ipynb')
print('01 actualizado', len(nb.cells))
