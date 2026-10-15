# -*- coding: utf-8 -*-
"""Generador del notebook 02_Clustering_DSMarket.ipynb (TFM DSMarket - Tarea 2).
Editar ESTE archivo y volver a correrlo en vez de tocar el .ipynb a mano.

Versión 2 (octubre 2026), tras la revisión con la tutora:
  - el número de grupos se elige con el método del codo (K de 2 a 14) y la silueta;
  - una sola segmentación de productos, con nombres ligados a los productos que contiene;
  - sin clustering de tiendas: con 10 tiendas se comparan directamente;
  - se quita la comparación con GMM y una de las dos variables redundantes.
"""
import os, sys
import nbformat as nbf

CELLS = []
def md(text): CELLS.append(('md', text.strip('\n')))
def code(text): CELLS.append(('code', text.strip('\n')))

md("""
# DSMarket — Segmentación de productos (Tarea 2)

**De:** Nicole, Data Science
**Para:** Joelle (Marketing Manager), Michelle (Chief Digital Officer)

Joelle pidió dos cosas:

1. **Agrupar productos que se comporten de manera similar**, para evaluar las campañas por grupo y no producto a producto. Preguntó cuántos grupos usar: ¿5, 10 o 20?
2. Saber si **un enfoque parecido sirve para comparar tiendas**.

Este notebook responde a las dos:

- Para los productos usamos **K-Means** y elegimos el número de grupos con el **método del codo** (probando de 2 a 14 grupos), apoyado en la **silueta**. El resultado es **una única segmentación** y cada grupo recibe un nombre que dice qué tipo de producto contiene.
- Para las tiendas **no aplicamos un algoritmo de agrupamiento**: con solo 10 tiendas, las comparamos directamente. La sección 5 explica por qué.

Parte de las mismas fuentes y decisiones de limpieza del EDA (`01_EDA_DSMarket.ipynb`, sección 6).
""")

md("## 1. Configuración e imports")

code("""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import seaborn as sns
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score, adjusted_rand_score
from sklearn.decomposition import PCA
from scipy.spatial.distance import cdist
import os

pd.set_option('display.max_columns', 50)
pd.set_option('display.width', 200)
RANDOM_STATE = 42
%matplotlib inline
""")

md("""
## 2. Paleta de marca DSMarket

Misma paleta validada del EDA (sección 2 de `01_EDA_DSMarket.ipynb`), repetida aquí para que el notebook se pueda ejecutar por separado.
""")

code("""
DSMARKET_NAVY = "#0a2a5c"
DSMARKET_BLUE = "#2a78d6"
DSMARKET_GOLD = "#eda100"
DSMARKET_GREEN = "#6a9f1f"

DSMARKET_BLUE_RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#2a78d6", "#1c5cab", "#0d366b"]
dsmarket_blues_cmap = LinearSegmentedColormap.from_list("dsmarket_blues", DSMARKET_BLUE_RAMP)
DIVERGENTE = LinearSegmentedColormap.from_list("dsmarket_div", [DSMARKET_GOLD, "#ffffff", DSMARKET_BLUE])

# un color por grupo de producto (6 grupos)
CLUSTER_PALETTE = [DSMARKET_BLUE, DSMARKET_GREEN, DSMARKET_NAVY, DSMARKET_GOLD, "#8a5fd6", "#d65f8a"]

sns.set_theme(style="whitegrid", rc={
    "axes.edgecolor": "#c3c2b7", "axes.labelcolor": "#0b0b0b", "text.color": "#0b0b0b",
    "xtick.color": "#52514e", "ytick.color": "#52514e", "grid.color": "#e1e0d9",
    "figure.facecolor": "white", "axes.facecolor": "white",
})
plt.rcParams["axes.titlecolor"] = DSMARKET_NAVY
plt.rcParams["axes.titleweight"] = "bold"
""")

md("""
## 3. Carga de datos

Mismas decisiones que en el EDA: se descartan las filas de `item_prices.csv` sin `yearweek`. Las 1.913 columnas de días se guardan como `int16` (el máximo vendido en un día es 763), lo que reduce la memoria a la cuarta parte.

El día de la semana se obtiene **de la fecha** (`dt.weekday`, 0 = lunes), no de la columna `weekday_int` del calendario, que numera la semana de sábado (1) a viernes (7).
""")

code("""
DATA_DIR = "data_dsmarket/data_dsmarket"

sales = pd.read_csv(f"{DATA_DIR}/item_sales.csv")
calendar = pd.read_csv(f"{DATA_DIR}/daily_calendar_with_events.csv")
calendar['date'] = pd.to_datetime(calendar['date'])

day_cols = [c for c in sales.columns if c.startswith('d_')]
sales[day_cols] = sales[day_cols].astype('int16')

prices = pd.read_csv(f"{DATA_DIR}/item_prices.csv")
prices_clean = prices.dropna(subset=['yearweek'])
prices_clean = prices_clean.assign(yearweek=prices_clean['yearweek'].astype(int))
del prices

dates_of_days = calendar.set_index('d')['date'].loc[day_cols]
weekdays = dates_of_days.dt.weekday.values      # 0 = lunes ... 6 = domingo
months = dates_of_days.dt.month.values
is_weekend = np.isin(weekdays, [5, 6])          # sábado y domingo
is_dec = months == 12

print(f"sales: {sales.shape} | prices_clean: {prices_clean.shape} | calendar: {calendar.shape}")
""")

md("""
## 4. Segmentación de productos

### 4.1. Variables de negocio

Igual que en la asignatura (donde los clientes de Olist se describían con variables tipo RFM), primero hay que traducir "cómo se vende un producto" a números. Para cada uno de los 3.049 productos, sumando las 10 tiendas:

| Variable | Pregunta que responde |
|---|---|
| `log_total_units` | ¿Cuánto vende en total? (en logaritmo, porque hay productos que venden 100 veces más que otros) |
| `cv_daily` | ¿Vende de forma estable o a saltos? (coeficiente de variación diario) |
| `zero_frac` | ¿Qué % de días no vende nada? |
| `weekend_lift` | ¿Cuánto más vende en fin de semana que entre semana? |
| `dec_lift` | ¿Cuánto más vende en diciembre que el resto del año? |
| `event_lift` | ¿Cuánto más vende en los eventos con pico (SuperBowl, Easter, Labor Day) que en un día normal? |
| `trend` | ¿Sus ventas suben o bajan con los años? |
| `avg_price` | ¿Es caro o barato? |

Dos decisiones sobre `event_lift`:
- Solo se usan los eventos que en el EDA mostraron un pico real. Navidad y Thanksgiving quedan fuera porque son días de cierre o de venta muy baja.
- Se compara con los **días sin ningún evento**, para que los días de cierre no rebajen la referencia.

La categoría y el departamento **no se usan para agrupar**: el objetivo es agrupar por comportamiento. Se usan después, en la ficha de los grupos (4.6), para describirlos y ponerles nombre.
""")

code("""
item_day = sales.groupby('item')[day_cols].sum()
vals = item_day.values.astype(float)

event_series = calendar.set_index('d')['event'].loc[day_cols]
labor_days = set()                               # Labor Day: primer lunes de septiembre
for y in dates_of_days.dt.year.unique():
    d = pd.Timestamp(year=int(y), month=9, day=1)
    while d.weekday() != 0:
        d += pd.Timedelta(days=1)
    labor_days.add(d)

is_peak_event = event_series.isin(['SuperBowl', 'Easter']).values | dates_of_days.isin(labor_days).values
is_any_event = (event_series.notna().values | dates_of_days.isin(labor_days).values
                | (dates_of_days.dt.month.eq(12) & dates_of_days.dt.day.eq(25)).values)
is_normal_day = ~is_any_event

avg_daily = vals.mean(axis=1)
x = np.arange(vals.shape[1]); x_c = x - x.mean()

item_feat = pd.DataFrame({
    'total_units': vals.sum(axis=1),
    'cv_daily': np.where(avg_daily > 0, vals.std(axis=1) / avg_daily, 0),
    'zero_frac': (vals == 0).mean(axis=1),
    'weekend_lift': vals[:, is_weekend].mean(axis=1) / vals[:, ~is_weekend].mean(axis=1),
    'dec_lift': vals[:, is_dec].mean(axis=1) / vals[:, ~is_dec].mean(axis=1),
    'event_lift': vals[:, is_peak_event].mean(axis=1) / vals[:, is_normal_day].mean(axis=1),
    'trend': (vals @ x_c) / (x_c ** 2).sum() / avg_daily,
}, index=item_day.index)
item_feat['avg_price'] = prices_clean.groupby('item')['sell_price'].mean()
item_feat['log_total_units'] = np.log1p(item_feat['total_units'])
item_feat['facturacion'] = item_feat['total_units'] * item_feat['avg_price']   # aproximada: unidades x precio medio

item_meta = sales[['item', 'category', 'department']].drop_duplicates().set_index('item')
item_feat = item_feat.join(item_meta).dropna(subset=['avg_price'])

CANDIDATAS = ['log_total_units', 'cv_daily', 'zero_frac', 'weekend_lift', 'dec_lift', 'event_lift', 'trend', 'avg_price']
print(f"Productos con todas las variables: {len(item_feat)} de {sales['item'].nunique()}")
item_feat[CANDIDATAS].describe().round(2)
""")

md("""
### 4.2. Revisión de variables: ¿alguna repite información?

Si dos variables miden casi lo mismo, esa idea cuenta **doble** en la distancia que usa K-Means y desequilibra el agrupamiento. Se revisa la correlación entre las 8 candidatas.
""")

code("""
corr = item_feat[CANDIDATAS].corr()

fig, ax = plt.subplots(figsize=(7.5, 6))
sns.heatmap(corr, annot=True, fmt='.2f', cmap=DIVERGENTE, center=0, vmin=-1, vmax=1,
            square=True, cbar_kws={'shrink': 0.8}, ax=ax, annot_kws={'size': 8})
ax.set_title('Correlación entre las 8 variables candidatas')
plt.tight_layout()
plt.show()

pares = (corr.where(np.triu(np.ones(corr.shape, dtype=bool), k=1)).stack()
         .rename('correlacion').reset_index().assign(abs=lambda d: d['correlacion'].abs())
         .sort_values('abs', ascending=False).drop(columns='abs').head(4))
pares.round(2)
""")

md("<<<DECISION_VARIABLES>>>")

code("""
FEAT_COLS = ['log_total_units', 'zero_frac', 'weekend_lift', 'dec_lift', 'event_lift', 'avg_price']
print(f"Variables finales ({len(FEAT_COLS)}): {FEAT_COLS}")
""")

md("""
### 4.3. Escalado: StandardScaler frente a RobustScaler

K-Means usa distancias, así que todas las variables tienen que estar en la misma escala. Si no, el precio (de 0,2 a 40 $) pesaría mucho más que un ratio que va de 0 a 2.

En la asignatura se usó `RobustScaler`, que escala con la mediana y los cuantiles para reducir la influencia de los valores extremos. Aquí hay valores extremos claros, como un producto que vende 7,7 veces más en diciembre que el resto del año, así que se prueban los dos escaladores en todo el rango de K.
""")

code("""
ESCALADORES = {'StandardScaler': StandardScaler(), 'RobustScaler': RobustScaler()}
K_RANGO = range(2, 15)

curvas = []
for nombre, esc in ESCALADORES.items():
    X = esc.fit_transform(item_feat[FEAT_COLS].values)
    for k in K_RANGO:
        km = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=50).fit(X)
        tamanos = np.bincount(km.labels_)
        curvas.append({'escalador': nombre, 'k': k, 'inercia': km.inertia_,
                       'silueta': silhouette_score(X, km.labels_),
                       'grupo_mas_pequeno': tamanos.min()})
curvas = pd.DataFrame(curvas)
curvas.pivot(index='k', columns='escalador', values='grupo_mas_pequeno').rename_axis(columns='productos en el grupo más pequeño')
""")

md("<<<DECISION_ESCALADO>>>")

code("""
X_items = StandardScaler().fit_transform(item_feat[FEAT_COLS].values)
curva = curvas[curvas['escalador'] == 'StandardScaler'].set_index('k')
""")

md("""
### 4.4. ¿Cuántos grupos? Método del codo y silueta

Es la idea central de la asignatura: se entrena K-Means con **K de 2 a 14** y se dibuja la **inercia** (la dispersión de los productos respecto al centro de su grupo). Al añadir grupos la inercia siempre baja; lo que se busca es el **codo**, el punto a partir del cual añadir más grupos apenas mejora.

Cuando la curva es suave y el codo no se ve a simple vista, se puede localizar midiendo qué punto de la curva se aleja más de la recta que une sus extremos. Como apoyo se usa la **silueta** (de -1 a 1, más alto es mejor): mide si cada producto está más cerca de su grupo que del grupo vecino.
""")

code("""
k_vals = curva.index.values.astype(float)
inercia = curva['inercia'].values
xn = (k_vals - k_vals.min()) / (k_vals.max() - k_vals.min())
yn = (inercia - inercia.min()) / (inercia.max() - inercia.min())
curva['distancia_a_la_recta'] = np.abs(yn - (1 - xn))      # cuanto mayor, más "codo" hay en ese punto

umbral = 0.9 * curva['distancia_a_la_recta'].max()
zona_codo = curva.index[curva['distancia_a_la_recta'] >= umbral].tolist()
K = int(curva.loc[zona_codo, 'silueta'].idxmax())
print(f"Zona del codo (≥90 % de la distancia máxima a la recta): K = {zona_codo}")
print(f"Dentro de esa zona, la mejor silueta es la de K = {K}")

fig, ax1 = plt.subplots(figsize=(11, 4.8))
ax1.axvspan(min(zona_codo) - 0.4, max(zona_codo) + 0.4, color=DSMARKET_GOLD, alpha=0.15, label='Zona del codo')
ax1.plot(curva.index, curva['inercia'], marker='o', color=DSMARKET_BLUE, label='Inercia')
ax1.set_xlabel('Número de grupos (K)')
ax1.set_ylabel('Inercia', color=DSMARKET_BLUE)
ax2 = ax1.twinx()
ax2.plot(curva.index, curva['silueta'], marker='s', linestyle='--', color=DSMARKET_GREEN, label='Silueta')
ax2.set_ylabel('Silueta', color=DSMARKET_GREEN)
ax2.grid(False)
ax1.axvline(K, color=DSMARKET_NAVY, linewidth=1.5)
ax1.annotate(f'K = {K}', xy=(K, curva.loc[K, 'inercia']), xytext=(K + 0.6, curva['inercia'].max() * 0.95),
             color=DSMARKET_NAVY, fontweight='bold', arrowprops=dict(arrowstyle='->', color=DSMARKET_NAVY))
ax1.set_xticks(list(K_RANGO))
lineas = ax1.get_legend_handles_labels(); lineas2 = ax2.get_legend_handles_labels()
ax1.legend(lineas[0] + lineas2[0], lineas[1] + lineas2[1], frameon=False, loc='upper right')
ax1.set_title('Método del codo: inercia y silueta según el número de grupos')
plt.tight_layout()
plt.show()

curva[['inercia', 'silueta', 'distancia_a_la_recta', 'grupo_mas_pequeno']].round(3)
""")

md("<<<DECISION_K>>>")

md("""
### 4.5. Modelo final y estabilidad

Se entrena K-Means con el K elegido. Como K-Means empieza con centros al azar, se comprueba que el resultado no dependa de la suerte: se repite con 10 semillas distintas y se compara cada resultado con el primero mediante el **índice de Rand ajustado** (ARI: 1 = grupos idénticos, 0 = coincidencia al azar).
""")

code("""
modelos = [KMeans(n_clusters=K, random_state=s, n_init=50).fit(X_items) for s in range(10)]
ari = [adjusted_rand_score(modelos[0].labels_, m.labels_) for m in modelos[1:]]
print(f"ARI medio entre 10 semillas: {np.mean(ari):.2f} (mínimo {np.min(ari):.2f})")

km_final = KMeans(n_clusters=K, random_state=RANDOM_STATE, n_init=50).fit(X_items)
item_feat['grupo_raw'] = km_final.labels_
""")

md("""
### 4.6. Ficha de los grupos y nombres

Como en la asignatura, se resume cada grupo en una **ficha**: tamaño, valores medios de las variables usadas y, además, **variables que no se usaron para agrupar** (categoría y facturación). Estas últimas sirven para describir qué productos hay en cada grupo y ponerle un **nombre de negocio**.

Para que los nombres no dependan del número que K-Means asigna a cada grupo (que cambia según la semilla), se asignan con reglas sobre la propia ficha: el grupo con más diciembre es el de Navidad, el de precio más alto es el premium, y así sucesivamente.
""")

code("""
perfil = item_feat.groupby('grupo_raw').agg(
    productos=('total_units', 'size'), unidades_medias=('total_units', 'mean'),
    zero_frac=('zero_frac', 'mean'), weekend_lift=('weekend_lift', 'mean'), dec_lift=('dec_lift', 'mean'),
    event_lift=('event_lift', 'mean'), avg_price=('avg_price', 'mean'), facturacion=('facturacion', 'sum'))

# --- nombres por reglas sobre la ficha (independientes de la numeración de K-Means) ---
pendientes = list(perfil.index)
def tomar(col, mayor=True):
    g = perfil.loc[pendientes, col].idxmax() if mayor else perfil.loc[pendientes, col].idxmin()
    pendientes.remove(g)
    return g
asignacion = {}
asignacion[tomar('dec_lift')] = 'Temporada de Navidad'
asignacion[tomar('avg_price')] = 'Accesorios y hogar de precio alto'
asignacion[tomar('unidades_medias')] = 'Alimentación de consumo diario'
asignacion[tomar('zero_frac')] = 'Compra ocasional en fechas señaladas'
asignacion[tomar('weekend_lift')] = 'Hogar de fin de semana'
asignacion[tomar('weekend_lift')] = 'Básicos de rotación lenta'
assert not pendientes, "quedan grupos sin nombre"

# numeración final: de mayor a menor facturación
orden = perfil['facturacion'].sort_values(ascending=False).index
nuevo_id = {g: i for i, g in enumerate(orden)}
item_feat['grupo'] = item_feat['grupo_raw'].map(nuevo_id)
item_feat['nombre_grupo'] = item_feat['grupo_raw'].map(asignacion)
NOMBRES = dict(zip(item_feat['grupo'], item_feat['nombre_grupo']))
NOMBRES = {k: NOMBRES[k] for k in sorted(NOMBRES)}
for g, n in NOMBRES.items():
    print(f"Grupo {g}: {n}")
""")

code("""
g = item_feat.groupby('grupo')
ficha = pd.DataFrame({
    'Grupo': [f'{i} · {NOMBRES[i]}' for i in sorted(NOMBRES)],
    'Productos': g.size().values,
    '% del catálogo': (g.size() / len(item_feat) * 100).values,
    '% de la facturación': (g['facturacion'].sum() / item_feat['facturacion'].sum() * 100).values,
    'Unidades medias (5 años)': g['total_units'].mean().values,
    '% días sin venta': (g['zero_frac'].mean() * 100).values,
    'Fin de semana vs. entre semana': g['weekend_lift'].mean().values,
    'Diciembre vs. resto del año': g['dec_lift'].mean().values,
    'Eventos vs. día normal': g['event_lift'].mean().values,
    'Precio medio ($)': g['avg_price'].mean().values,
}).set_index('Grupo')
categorias = pd.crosstab(item_feat['grupo'], item_feat['category'], normalize='index') * 100
categorias.index = ficha.index
categorias.columns = [f'% {c}' for c in categorias.columns]
ficha = ficha.join(categorias)

(ficha.T.style.format('{:,.2f}')
      .background_gradient(cmap=dsmarket_blues_cmap, axis=1))
""")

md("<<<LECTURA_GRUPOS>>>")

code("""
pca = PCA(n_components=2, random_state=RANDOM_STATE)
coords = pca.fit_transform(X_items)
var_exp = pca.explained_variance_ratio_

fig, axes = plt.subplots(1, 2, figsize=(14, 5.2), gridspec_kw={'width_ratios': [1.6, 1]})
ax = axes[0]
for gr in sorted(NOMBRES):
    m = (item_feat['grupo'] == gr).values
    ax.scatter(coords[m, 0], coords[m, 1], s=9, alpha=0.5, color=CLUSTER_PALETTE[gr], label=f'{gr} · {NOMBRES[gr]}')
ax.set_xlabel(f'Componente 1 ({var_exp[0]:.0%} de la varianza)')
ax.set_ylabel(f'Componente 2 ({var_exp[1]:.0%} de la varianza)')
ax.set_title('Productos por grupo (proyección PCA a 2 dimensiones)')
ax.legend(frameon=False, markerscale=2.5, fontsize=8, loc='best')

ax2 = axes[1]
tabla = ficha[['% del catálogo', '% de la facturación']].iloc[::-1]
y = np.arange(len(tabla))
ax2.barh(y + 0.2, tabla['% del catálogo'], height=0.4, color='#9ec5f4', label='% del catálogo')
ax2.barh(y - 0.2, tabla['% de la facturación'], height=0.4, color=DSMARKET_BLUE, label='% de la facturación')
ax2.set_yticks(y); ax2.set_yticklabels([t.split(' · ')[1] for t in tabla.index], fontsize=9)
for yy, v in zip(y - 0.2, tabla['% de la facturación']):
    ax2.text(v, yy, f' {v:.0f}%', va='center', fontsize=8)
ax2.set_xlabel('%')
ax2.set_title('Peso de cada grupo')
ax2.legend(frameon=False, fontsize=8, loc='lower right')
plt.tight_layout()
plt.show()
print(f"Las dos componentes resumen el {var_exp.sum():.0%} de la información de las {len(FEAT_COLS)} variables.")
""")

md("""
### 4.7. Respuesta a Joelle: ¿5, 10 o 20 grupos?

Joelle propuso tres valores. Se comparan con el elegido por el codo:
""")

code("""
extra = []
for k in [5, K, 10, 20]:
    if k in curva.index:
        r = curva.loc[k]
        extra.append({'K': k, 'silueta': r['silueta'], 'grupo más pequeño': int(r['grupo_mas_pequeno']), 'origen': 'codo' if k == K else 'propuesta de Joelle'})
    else:
        km = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=50).fit(X_items)
        extra.append({'K': k, 'silueta': silhouette_score(X_items, km.labels_),
                      'grupo más pequeño': int(np.bincount(km.labels_).min()), 'origen': 'propuesta de Joelle'})
pd.DataFrame(extra).set_index('K').round(3)
""")

md("<<<RESPUESTA_JOELLE>>>")

md("""
### 4.8. Un caso que ilustra el grupo de Navidad: `SUPERMARKET_3_069`

Dentro del grupo de Navidad destaca un producto con la mayor subida de diciembre de todo el catálogo.
""")

code("""
caso = item_feat['dec_lift'].idxmax()
print(f"Producto con más subida en diciembre: {caso} (grupo {item_feat.loc[caso, 'grupo']} · {item_feat.loc[caso, 'nombre_grupo']})")
print(f"Vende {item_feat.loc[caso, 'dec_lift']:.1f} veces más en diciembre que el resto del año.")
print()
serie = pd.Series(item_day.loc[caso].values, index=dates_of_days.values)
print("Sus 5 mejores días en cinco años:")
print(serie.sort_values(ascending=False).head(5).to_string())

fig, ax = plt.subplots(figsize=(12, 3.6))
ax.plot(serie.index, serie.values, color=DSMARKET_BLUE, linewidth=0.8)
top = serie.sort_values(ascending=False).head(4)
ax.scatter(top.index, top.values, color=DSMARKET_GOLD, zorder=3, s=35, label='Mejores días')
ax.set_title(f'{caso}: ventas diarias (suma de las 10 tiendas)')
ax.set_ylabel('Unidades')
ax.legend(frameon=False)
plt.tight_layout()
plt.show()
""")

md("<<<CASO_069>>>")

md("""
### 4.9. Guardar la segmentación

Se guarda el grupo de cada producto para usarlo en la predicción de ventas (Tarea 3) y en la reposición (Tarea 4).
""")

code("""
os.makedirs('cache_forecast', exist_ok=True)
salida = item_feat[['grupo', 'nombre_grupo']]
salida.to_csv('cache_forecast/segmentacion_productos.csv')
print(f"Guardado cache_forecast/segmentacion_productos.csv: {len(salida)} productos")
salida['nombre_grupo'].value_counts()
""")

md("""
## 5. Tiendas: comparación directa en lugar de clustering

### 5.1. Por qué no se agrupan las tiendas con un algoritmo

Joelle preguntó si agrupar tiendas también tendría sentido. **Con estos datos, no**, por tres motivos:

1. **Solo hay 10 tiendas.** Un algoritmo de agrupamiento tiene sentido cuando hay demasiados elementos para compararlos a simple vista, como los 3.049 productos. Diez tiendas caben en una tabla.
2. **Habría más variables que tiendas.** Para describir el perfil de una tienda hacen falta unas 12 variables (volumen, estabilidad, fin de semana, diciembre, precio y el peso de cada uno de los 7 departamentos). Con 12 dimensiones y 10 puntos, las distancias pierden sentido: es la **maldición de la dimensionalidad** vista en la asignatura. Cualquier agrupación saldría inestable y dependería de qué tiendas entren en el cálculo.
3. **Lo que interesa a negocio se ve mejor comparando directamente**: qué tienda se parece a cuál y en qué.

Por eso se responde a Joelle con una **tabla comparativa** y una medida de **parecido entre tiendas**.
""")

code("""
store_day = sales.groupby('store_code')[day_cols].sum()
vals_s = store_day.values.astype(float)
media_s = vals_s.mean(axis=1)

store_feat = pd.DataFrame({
    'ventas_dia': media_s,
    'cv_daily': vals_s.std(axis=1) / media_s,
    'weekend_lift': vals_s[:, is_weekend].mean(axis=1) / vals_s[:, ~is_weekend].mean(axis=1),
    'dec_lift': vals_s[:, is_dec].mean(axis=1) / vals_s[:, ~is_dec].mean(axis=1),
}, index=store_day.index)

# índice de precio: cuánto más cara o barata es la tienda que la media de cada producto (EDA, sección 10.1)
precio_item_tienda = prices_clean.groupby(['item', 'store_code'])['sell_price'].mean().unstack('store_code')
relativo = precio_item_tienda.div(precio_item_tienda.mean(axis=1), axis=0)
store_feat['indice_precio_pct'] = (relativo.mean(axis=0) - 1) * 100

# peso de cada categoría en las unidades vendidas
tot = sales[['store_code', 'category']].assign(u=sales[day_cols].sum(axis=1))
mix = tot.groupby(['store_code', 'category'])['u'].sum().unstack('category')
mix = mix.div(mix.sum(axis=1), axis=0) * 100
store_feat['pct_supermarket'] = mix['SUPERMARKET']
store_feat['pct_hogar'] = mix['HOME_&_GARDEN']
store_feat['pct_accesorios'] = mix['ACCESORIES']

meta_t = sales[['store_code', 'store', 'region']].drop_duplicates().set_index('store_code')
store_feat = meta_t.join(store_feat)
store_feat['store'] = store_feat['store'].str.replace('_', ' ')

ETIQUETAS = {'ventas_dia': 'Unidades por día', 'cv_daily': 'Variabilidad diaria',
             'weekend_lift': 'Fin de semana vs. entre semana', 'dec_lift': 'Diciembre vs. resto del año',
             'indice_precio_pct': 'Índice de precio (%)', 'pct_supermarket': '% alimentación',
             'pct_hogar': '% hogar', 'pct_accesorios': '% accesorios'}
tabla_t = store_feat.set_index(['region', 'store']).rename(columns=ETIQUETAS)
tabla_t.style.format('{:,.2f}').background_gradient(cmap=dsmarket_blues_cmap, axis=0)
""")

md("""
### 5.2. Mapa de calor: en qué se diferencia cada tienda

Cada celda indica cuánto se aleja la tienda de la media de las 10 en esa variable (en desviaciones típicas): azul por encima de la media y dorado por debajo.
""")

code("""
PERFIL_T = ['cv_daily', 'weekend_lift', 'dec_lift', 'indice_precio_pct', 'pct_supermarket', 'pct_hogar']
z = (store_feat[PERFIL_T] - store_feat[PERFIL_T].mean()) / store_feat[PERFIL_T].std()
z.index = store_feat['store'] + ' (' + store_feat['region'].map({'New York': 'NY', 'Boston': 'BOS', 'Philadelphia': 'PHI'}) + ')'

fig, ax = plt.subplots(figsize=(9, 5.5))
sns.heatmap(z.rename(columns=ETIQUETAS), annot=True, fmt='.1f', cmap=DIVERGENTE, center=0,
            vmin=-2.5, vmax=2.5, cbar_kws={'label': 'Desviaciones respecto a la media'}, ax=ax)
ax.set_title('Perfil de cada tienda respecto a la media de las 10')
ax.set_ylabel('')
plt.xticks(rotation=30, ha='right')
plt.tight_layout()
plt.show()
""")

md("""
### 5.3. ¿Qué tienda se parece más a cuál?

Se mide la distancia entre tiendas con las variables de **perfil** de la tabla anterior. El volumen de ventas se deja fuera porque mide el tamaño de la tienda, no su forma de vender: una tienda grande y una pequeña pueden tener el mismo perfil.
""")

code("""
D = pd.DataFrame(cdist(z.values, z.values), index=z.index, columns=z.index)
parecido = []
for t in D.index:
    otras = D.loc[t].drop(t).sort_values()
    parecido.append({'Tienda': t, 'Más parecida': otras.index[0], 'Distancia': otras.iloc[0],
                     'Segunda más parecida': otras.index[1]})
parecido = pd.DataFrame(parecido).set_index('Tienda')

fig, ax = plt.subplots(figsize=(8, 6.5))
sns.heatmap(D, annot=True, fmt='.1f', cmap=dsmarket_blues_cmap.reversed(), square=True,
            cbar_kws={'label': 'Distancia (menor = más parecidas)', 'shrink': 0.8}, ax=ax, annot_kws={'size': 7})
ax.set_title('Parecido entre tiendas')
ax.set_xlabel(''); ax.set_ylabel('')
plt.tight_layout()
plt.show()
parecido.round(2)
""")

md("<<<LECTURA_TIENDAS>>>")

md("<<<CONCLUSIONES>>>")

# =========================================================================== textos
NARRATIVA = {}
TEXTOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'textos_notebook_02.py')
if os.path.exists(TEXTOS):
    exec(open(TEXTOS, encoding='utf-8').read())

CELLS = [(k, NARRATIVA.get(s.strip(), s)) for k, s in CELLS]
faltantes = [s for k, s in CELLS if s.strip().startswith('<<<')]
if faltantes and '--borrador' not in sys.argv:
    raise SystemExit(f"placeholders sin texto: {faltantes}")

nb = nbf.v4.new_notebook()
nb['cells'] = [nbf.v4.new_markdown_cell(src.strip()) if kind == 'md' else nbf.v4.new_code_cell(src.strip())
               for kind, src in CELLS]
nb['metadata'] = {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
                  'language_info': {'name': 'python'}}
out = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else '02_Clustering_DSMarket.ipynb'
nbf.write(nb, out)
print(f"escrito: {out} ({len(CELLS)} celdas)")
