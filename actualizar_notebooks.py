# -*- coding: utf-8 -*-
"""Añade la sección de actualización (nueva segmentación de la Tarea 2) a los notebooks 03 y 04.

Los notebooks 03 y 04 no se pueden reejecutar enteros desde el repositorio (dependen de resultados
guardados que generó código que no está en el repo), así que se conservan sus celdas y salidas
originales y solo se ejecutan las celdas nuevas, que son autocontenidas.
"""
import sys, json, copy
import nbformat
from nbclient import NotebookClient

NOTA_03 = """
> **Nota de actualización (octubre 2026).** La segmentación de la Tarea 2 se rehízo tras la revisión con la tutora: ahora hay **6 grupos de producto** elegidos con el método del codo y **ya no se agrupan las tiendas**. Las secciones 1 a 14 de este notebook se calcularon con la segmentación anterior (5 y 10 grupos de producto y 3 grupos de tienda). La **sección 15**, al final, reentrena el modelo principal con la segmentación actual y comprueba si cambia algo. La **sección 16** recoge la revisión de la tutoría: ejemplos concretos de predicción, el error medido por semanas y los eventos tratados a nivel semanal.
"""

MD_03_INTRO = """
## 15. Actualización: el modelo con la segmentación actual de la Tarea 2

La Tarea 2 se rehízo con estos cambios:
- **6 grupos de producto** elegidos con el método del codo, en lugar de las dos segmentaciones anteriores (5 y 10 grupos) que no encajaban entre sí;
- **sin grupos de tienda**: con 10 tiendas se comparan directamente, sin algoritmo.

En el modelo eso significa cambiar tres variables (`cluster_k5`, `cluster_k10` y `store_cluster`) por una sola (`grupo_producto`). La tienda y la ciudad siguen en el modelo como variables propias (`store_id` y `region_id`).

Para saber si el cambio afecta a los resultados, se reentrena el modelo principal (**LightGBM por bloques semanales**, sección 6) en los mismos 3 tramos de validación con las dos versiones de las variables y se comparan. El código está en `forecast_segmentacion.py`: es autocontenido y lee directamente los CSV originales.
"""

CODE_03_A = """
import forecast_segmentacion as fs

V_, P_, cs_, cal_, meta_, folds_ = fs.cargar()
filas_act, preds_act, imps_act = [], {}, {}
for config in ['anterior', 'actual']:
    for f, (s_, e_) in enumerate(folds_):
        r = fs.entrenar_fold(config, f, V_, P_, cs_, cal_, meta_, folds_)
        y_ = V_[:, s_:e_].astype(np.float32); h_ = V_[:, :s_].astype(np.float32)
        filas_act.append({'segmentación': config, 'fold': f + 1, 'MAE': fs.mae(y_, r['pred']),
                          'RMSSE': float(np.nanmean(fs.rmsse_por_serie(y_, r['pred'], h_))),
                          'WRMSSE': fs.wrmsse(y_, r['pred'], h_, P_[:, :s_])})
        preds_act[(config, f)] = r['pred']
        imps_act[(config, f)] = r['importancia']
comp = pd.DataFrame(filas_act)
tabla_comp = comp.pivot(index='fold', columns='segmentación', values='WRMSSE')[['anterior', 'actual']]
tabla_comp.loc['media'] = tabla_comp.mean()
tabla_comp['diferencia %'] = (tabla_comp['actual'] - tabla_comp['anterior']) / tabla_comp['anterior'] * 100
print('WRMSSE de LightGBM por bloques semanales (menor es mejor)')
tabla_comp.round(4)
"""

CODE_03_B = """
# ¿cuánto pesan las variables de segmentación dentro del modelo?
peso = {}
for config, cols in fs.CONFIGURACIONES.items():
    imp = pd.concat([imps_act[(config, f)] for f in range(3)], axis=1).mean(axis=1)
    peso[config] = {'variables de segmentación': ', '.join(cols),
                    '% de la importancia': imp[cols].sum() / imp.sum() * 100,
                    '% de rmean_28': imp['rmean_28'] / imp.sum() * 100}
pd.DataFrame(peso).T.round(2)
"""

MD_03_GRUPOS = """
### 15.1. ¿Dónde funciona el modelo? Error por grupo de producto (segmentación actual)

Se repite el análisis de la sección 10 con los 6 grupos nuevos: RMSSE del modelo frente a la media móvil de 28 días, en los 3 tramos. Recordatorio: el RMSSE compara con el error de predecir un solo día adelante con el dato de ayer, que es un problema más fácil; lo que importa es la comparación entre el modelo y la referencia.
"""

CODE_03_C = """
filas_g = []
for f, (s_, e_) in enumerate(folds_):
    y_ = V_[:, s_:e_].astype(np.float32); h_ = V_[:, :s_].astype(np.float32)
    media28 = np.repeat(V_[:, s_-28:s_].mean(axis=1, keepdims=True), e_ - s_, axis=1).astype(np.float32)
    media28 = np.where(np.isnan(P_[:, s_:e_]), 0, media28)
    r_mod = fs.rmsse_por_serie(y_, preds_act[('actual', f)], h_)
    r_base = fs.rmsse_por_serie(y_, media28, h_)
    filas_g.append(pd.DataFrame({'grupo': meta_['nombre_grupo'].values, 'RMSSE_modelo': r_mod,
                                 'RMSSE_media_movil': r_base, 'unidades_dia': y_.mean(axis=1)}))
err_g = pd.concat(filas_g)
tabla_g = err_g.groupby('grupo').agg(series=('grupo', 'size'), RMSSE_modelo=('RMSSE_modelo', 'mean'),
                                     RMSSE_media_movil=('RMSSE_media_movil', 'mean'),
                                     unidades_dia=('unidades_dia', 'sum'))
tabla_g['series'] = tabla_g['series'] // 3
tabla_g['unidades_dia'] = tabla_g['unidades_dia'] / 3
tabla_g['% de las unidades'] = tabla_g['unidades_dia'] / tabla_g['unidades_dia'].sum() * 100
tabla_g = tabla_g.sort_values('RMSSE_modelo')

fig, ax = plt.subplots(figsize=(10, 4.2))
colores = [DSMARKET_GOLD if v > 1 else DSMARKET_BLUE for v in tabla_g['RMSSE_modelo']]
ax.barh(tabla_g.index[::-1], tabla_g['RMSSE_modelo'][::-1], color=colores[::-1])
ax.axvline(1, color='#52514e', linestyle='--', linewidth=1)
for i, v in enumerate(tabla_g['RMSSE_modelo'][::-1]):
    ax.text(v, i, f' {v:.3f}', va='center', fontsize=9)
ax.set_title('Error del modelo por grupo de producto (RMSSE, media de los 3 tramos)', color=DSMARKET_NAVY, fontweight='bold')
plt.tight_layout(); plt.show()
tabla_g.round(3)
"""

CODE_16_A = """
import forecast_semanal as fw
EJEMPLOS = ['SUPERMARKET_2_371_PHI_3', 'SUPERMARKET_3_465_NYC_1']   # uno de venta diaria y uno de venta irregular
s_, e_ = folds_[2]                                                  # última ventana: 28-mar a 24-abr de 2016
fechas_ = pd.to_datetime(cal_['date'].values)
pred_ult = preds_act[('actual', 2)]
HIST = 56                                                           # 8 semanas de historia antes del corte

fig, axes = plt.subplots(2, 2, figsize=(15, 8), gridspec_kw={'width_ratios': [2.3, 1]})
filas_ej = []
for fila, serie_id in enumerate(EJEMPLOS):
    i = int(np.nonzero(meta_['id'].values == serie_id)[0][0])
    grupo = meta_['nombre_grupo'].iloc[i]
    real = V_[i, s_:e_].astype(float); pred = pred_ult[i]
    ax = axes[fila, 0]
    ax.plot(fechas_[s_-HIST:s_+1], V_[i, s_-HIST:s_+1], color='#9a9a96', linewidth=1.3, label='Lo que teníamos (histórico)')
    ax.plot(fechas_[s_:e_], real, color=DSMARKET_NAVY, linewidth=2, marker='o', markersize=3.5, label='Lo que pasó de verdad')
    ax.plot(fechas_[s_:e_], pred, color=DSMARKET_GOLD, linewidth=2.2, linestyle='--', label='Lo que predijo el modelo')
    ax.axvline(fechas_[s_], color='#52514e', linestyle=':', linewidth=1)
    ax.text(fechas_[s_], ax.get_ylim()[1] * 0.95, '  día de la predicción', fontsize=9, color='#52514e', va='top')
    ax.set_title(f'{serie_id}  ·  {grupo}', color=DSMARKET_NAVY, fontweight='bold', loc='left')
    ax.set_ylabel('Unidades / día')
    if fila == 0: ax.legend(frameon=False, loc='upper left', fontsize=9)
    # la misma serie sumada por semanas
    rs, ps = fw.a_semanas(real[None])[0], fw.a_semanas(pred[None])[0]
    ax = axes[fila, 1]
    x = np.arange(4)
    ax.bar(x - 0.2, rs, width=0.4, color=DSMARKET_NAVY, label='Real')
    ax.bar(x + 0.2, ps, width=0.4, color=DSMARKET_GOLD, label='Predicho')
    for k in range(4):
        ax.text(x[k] - 0.2, rs[k], f'{rs[k]:.0f}', ha='center', va='bottom', fontsize=8)
        ax.text(x[k] + 0.2, ps[k], f'{ps[k]:.0f}', ha='center', va='bottom', fontsize=8)
    ax.set_xticks(x); ax.set_xticklabels([f'Semana {k+1}' for k in range(4)])
    ax.set_title('Por semanas', color=DSMARKET_NAVY, fontweight='bold', loc='left')
    if fila == 0: ax.legend(frameon=False, fontsize=9)
    filas_ej.append({'serie': serie_id, 'grupo': grupo,
                     'días sin venta (%)': (real == 0).mean() * 100,
                     'error por día (WAPE %)': fw.wape(real, pred),
                     'error por semana (WAPE %)': fw.wape(rs, ps),
                     'vendido en 4 semanas': real.sum(), 'predicho en 4 semanas': pred.sum()})
plt.suptitle('Ejemplos concretos: lo que teníamos, lo que pasó y lo que predijo el modelo (28-mar a 24-abr de 2016)',
             color=DSMARKET_NAVY, fontweight='bold', y=1.0)
plt.tight_layout(); plt.show()
pd.DataFrame(filas_ej).set_index('serie').round(1)
"""

CODE_16_B = """
# ¿Cuántos ceros hay si miramos días y si miramos semanas?
filas_m = []
for f, (s_, e_) in enumerate(folds_):
    y_ = V_[:, s_:e_].astype(np.float32)
    activa = ~np.isnan(P_[:, s_:e_])
    activa_sem = activa.reshape(len(y_), -1, 7).all(axis=2)
    base = fw.media_movil_28(V_, P_, s_, e_)
    pm = preds_act[('actual', f)]
    filas_m.append({'ventana': fw.NOMBRE_VENTANA[f'fold{f}'],
                    'días sin venta (%)': (y_[activa] == 0).mean() * 100,
                    'semanas sin venta (%)': (fw.a_semanas(y_)[activa_sem] == 0).mean() * 100,
                    'WAPE diario modelo': fw.wape(y_, pm), 'WAPE diario media móvil': fw.wape(y_, base),
                    'WAPE semanal modelo': fw.wape(fw.a_semanas(y_), fw.a_semanas(pm)),
                    'WAPE semanal media móvil': fw.wape(fw.a_semanas(y_), fw.a_semanas(base))})
tabla_m = pd.DataFrame(filas_m).set_index('ventana')
tabla_m.loc['media'] = tabla_m.mean()
tabla_m.round(1)
"""

CODE_16_C = """
# Error semanal por grupo de producto (media de las 3 ventanas)
filas_gw = []
for f, (s_, e_) in enumerate(folds_):
    ys = fw.a_semanas(V_[:, s_:e_].astype(np.float32)); ps = fw.a_semanas(preds_act[('actual', f)])
    bs = fw.a_semanas(fw.media_movil_28(V_, P_, s_, e_))
    for g, idx in meta_.groupby('nombre_grupo').indices.items():
        filas_gw.append({'grupo': g, 'WAPE semanal modelo': fw.wape(ys[idx], ps[idx]),
                         'WAPE semanal media móvil': fw.wape(ys[idx], bs[idx]),
                         'semanas sin venta (%)': (ys[idx] == 0).mean() * 100})
tabla_gw = pd.DataFrame(filas_gw).groupby('grupo').mean().sort_values('WAPE semanal modelo')
tabla_gw['mejora sobre media móvil (puntos)'] = tabla_gw['WAPE semanal media móvil'] - tabla_gw['WAPE semanal modelo']

fig, ax = plt.subplots(figsize=(10, 4.2))
yy = np.arange(len(tabla_gw))
ax.barh(yy + 0.2, tabla_gw['WAPE semanal media móvil'], height=0.4, color='#c3c2bd', label='Media móvil 28 días')
ax.barh(yy - 0.2, tabla_gw['WAPE semanal modelo'], height=0.4, color=DSMARKET_BLUE, label='Modelo')
for k, v in enumerate(tabla_gw['WAPE semanal modelo']):
    ax.text(v, k - 0.2, f' {v:.0f}%', va='center', fontsize=9)
ax.set_yticks(yy); ax.set_yticklabels(tabla_gw.index); ax.invert_yaxis()
ax.set_xlabel('% de las unidades de la semana en que se equivoca (menor es mejor)')
ax.set_title('Error semanal por grupo de producto (WAPE, 3 ventanas)', color=DSMARKET_NAVY, fontweight='bold')
ax.set_xlim(0, tabla_gw[['WAPE semanal modelo', 'WAPE semanal media móvil']].values.max() * 1.12)
ax.legend(frameon=False, loc='upper right')
plt.tight_layout(); plt.show()
tabla_gw.round(1)
"""

CODE_16_D = """
# Comparación: modelo de la sección 15 frente al mismo modelo con las 4 variables de evento semanal
V16 = fw.ventanas(cal_, folds_)
filas_ev, imp_ev = [], []
for nombre, (s_, e_) in V16.items():
    y_ = V_[:, s_:e_].astype(np.float32); h_ = V_[:, :s_].astype(np.float32)
    for config in fw.CONFIGS:
        r = fw.entrenar(config, nombre, (s_, e_), V_, P_, cs_, cal_, meta_, None)
        filas_ev.append({'ventana': fw.NOMBRE_VENTANA[nombre], 'modelo': config,
                         'WRMSSE': fs.wrmsse(y_, r['pred'], h_, P_[:, :s_]),
                         'WAPE semanal': fw.wape(fw.a_semanas(y_), fw.a_semanas(r['pred']))})
        if config == 'eventos_semanales':
            imp_ev.append(r['importancia'] / r['importancia'].sum() * 100)
ev = pd.DataFrame(filas_ev)
tabla_ev = ev.pivot(index='ventana', columns='modelo', values=['WRMSSE', 'WAPE semanal'])
tabla_ev = tabla_ev.reindex([fw.NOMBRE_VENTANA[k] for k in V16])
tabla_ev.round(4)
"""

CODE_16_E = """
# ¿Cuánto pesan las variables nuevas dentro del modelo? (% de la importancia, media de las 5 ventanas)
imp_ev_m = pd.concat(imp_ev, axis=1).mean(axis=1)
pd.DataFrame({'% de la importancia': imp_ev_m[fw.EXTRA_SEMANAL + ['event']].round(2)})
"""

CODE_16_F = """
# Diciembre día a día: total de la cadena, con y sin eventos semanales
s_, e_ = V16['dic2015']
f_dic = pd.to_datetime(cal_['date'].values[s_:e_])
real_d = V_[:, s_:e_].sum(axis=0)
pa = fw.entrenar('actual', 'dic2015', (s_, e_), V_, P_, cs_, cal_, meta_, None)['pred'].sum(axis=0)
pe = fw.entrenar('eventos_semanales', 'dic2015', (s_, e_), V_, P_, cs_, cal_, meta_, None)['pred'].sum(axis=0)
fig, ax = plt.subplots(figsize=(13, 4.5))
ax.plot(f_dic, real_d, color=DSMARKET_NAVY, linewidth=2, marker='o', markersize=4, label='Real')
ax.plot(f_dic, pa, color='#9a9a96', linewidth=1.8, linestyle='--', label='Modelo sección 15')
ax.plot(f_dic, pe, color=DSMARKET_GOLD, linewidth=2, linestyle='--', label='Con eventos semanales')
ax.set_title('Diciembre 2015: total diario real y predicho', color=DSMARKET_NAVY, fontweight='bold')
ax.set_ylabel('Unidades / día'); ax.legend(frameon=False)
plt.tight_layout(); plt.show()
sem_dic = pd.DataFrame({'semana': [f'{f_dic[7*k].date()} a {f_dic[7*k+6].date()}' for k in range(4)],
                        'real': fw.a_semanas(real_d[None])[0], 'modelo sección 15': fw.a_semanas(pa[None])[0],
                        'con eventos semanales': fw.a_semanas(pe[None])[0]}).set_index('semana')
for c in ['modelo sección 15', 'con eventos semanales']:
    sem_dic[f'error {c} (%)'] = (sem_dic[c] - sem_dic['real']) / sem_dic['real'] * 100
sem_dic.round(1)
"""

CODE_16_G = """
# Las 4 versiones en las 5 ventanas
ORDEN_CFG = ['actual', 'eventos_semanales', 'actual_400d', 'eventos_semanales_400d']
NOMBRE_CFG = {'actual': '180 días', 'eventos_semanales': '180 días + eventos sem.',
              'actual_400d': '400 días', 'eventos_semanales_400d': '400 días + eventos sem.'}
filas_l = []
for nombre, (s_, e_) in V16.items():
    y_ = V_[:, s_:e_].astype(np.float32); h_ = V_[:, :s_].astype(np.float32)
    for config in ORDEN_CFG:
        r = fw.entrenar(config, nombre, (s_, e_), V_, P_, cs_, cal_, meta_, None)
        filas_l.append({'ventana': fw.NOMBRE_VENTANA[nombre], 'versión': NOMBRE_CFG[config],
                        'WRMSSE': fs.wrmsse(y_, r['pred'], h_, P_[:, :s_]),
                        'WAPE semanal': fw.wape(fw.a_semanas(y_), fw.a_semanas(r['pred']))})
larg = pd.DataFrame(filas_l)
cols = [NOMBRE_CFG[c] for c in ORDEN_CFG]
filas_idx = [fw.NOMBRE_VENTANA[k] for k in V16]
t_w = larg.pivot(index='ventana', columns='versión', values='WRMSSE').reindex(filas_idx)[cols]
t_w.loc['media feb-abr'] = t_w.iloc[:3].mean()
t_a = larg.pivot(index='ventana', columns='versión', values='WAPE semanal').reindex(filas_idx)[cols]
t_a.loc['media feb-abr'] = t_a.iloc[:3].mean()
print('WRMSSE (menor es mejor)'); display(t_w.round(4))
print('WAPE semanal, % (menor es mejor)'); display(t_a.round(1))
"""

CODE_16_H = """
# Diciembre con 400 días de historia
s_, e_ = V16['dic2015']
p400 = fw.entrenar('eventos_semanales_400d', 'dic2015', (s_, e_), V_, P_, cs_, cal_, meta_, None)['pred'].sum(axis=0)
fig, ax = plt.subplots(figsize=(13, 4.5))
ax.plot(f_dic, real_d, color=DSMARKET_NAVY, linewidth=2, marker='o', markersize=4, label='Real')
ax.plot(f_dic, pa, color='#9a9a96', linewidth=1.8, linestyle='--', label='180 días (modelo sección 15)')
ax.plot(f_dic, p400, color=DSMARKET_GOLD, linewidth=2.2, linestyle='--', label='400 días + eventos semanales')
ax.set_title('Diciembre 2015: total diario real y predicho', color=DSMARKET_NAVY, fontweight='bold')
ax.set_ylabel('Unidades / día'); ax.legend(frameon=False, loc='lower left')
plt.tight_layout(); plt.show()
sem_dic['400 días + eventos semanales'] = fw.a_semanas(p400[None])[0]
sem_dic['error 400 días + eventos (%)'] = (sem_dic['400 días + eventos semanales'] - sem_dic['real']) / sem_dic['real'] * 100
sem_dic[['real', 'modelo sección 15', '400 días + eventos semanales',
         'error modelo sección 15 (%)', 'error 400 días + eventos (%)']].round(1)
"""

CODE_16_I = """
# Modelo final: 400 días de historia + eventos semanales + grupo de producto actual (modelo_final.py)
import modelo_final as mf
s_, e_ = folds_[2]
y_ = V_[:, s_:e_].astype(np.float32); h_ = V_[:, :s_].astype(np.float32)
fm = np.load('cache_forecast/final_eval_media.npy'); fp = np.load('cache_forecast/final_eval_p90.npy')
valido = ~np.isnan(P_[:, s_:e_])
def pinball(y, q, a=0.9):
    d = y - q
    return float(np.mean(np.maximum(a * d, (a - 1) * d)))
comp_final = pd.DataFrame({
    'modelo de la sección 15 (180 días)': {'WRMSSE': fs.wrmsse(y_, preds_act[('actual', 2)], h_, P_[:, :s_]),
                                           'WAPE semanal %': fw.wape(fw.a_semanas(y_), fw.a_semanas(preds_act[('actual', 2)]))},
    'modelo final (400 días + eventos semanales)': {'WRMSSE': fs.wrmsse(y_, fm, h_, P_[:, :s_]),
                                                    'WAPE semanal %': fw.wape(fw.a_semanas(y_), fw.a_semanas(fm))}}).T
print(f"Ventana 28-mar a 24-abr de 2016 (la que simula el notebook 04)")
print(f"Cobertura del percentil 90 (días-producto): {(y_[valido] <= fp[valido]).mean():.1%}  (objetivo 90 %)")
print(f"Cobertura de la predicción media:           {(y_[valido] <= fm[valido]).mean():.1%}")
print(f"Pérdida pinball del p90: {pinball(y_[valido], fp[valido]):.4f}  ·  usando la media como p90: {pinball(y_[valido], fm[valido]):.4f}")
print(f"Unidades según la media: {fm[valido].sum():,.0f}  ·  según el p90: {fp[valido].sum():,.0f}  ·  demanda real: {y_[valido].sum():,.0f}")
comp_final.round(4)
"""

CODE_16_J = """
# La entrega: los 28 días siguientes al último día con datos
pred_futuro = np.load('cache_forecast/final_futuro_media.npy')
p90_futuro = np.load('cache_forecast/final_futuro_p90.npy')
fechas_fut = pd.date_range(fechas_[-1] + pd.Timedelta(days=1), periods=28)
total_hist = pd.Series(V_.sum(axis=0), index=fechas_)

fig, ax = plt.subplots(figsize=(13, 4.5))
ax.plot(total_hist.index[-90:], total_hist.values[-90:], color='#8a8a8a', linewidth=1, label='Ventas reales')
ax.plot(fechas_fut, pred_futuro.sum(axis=0), color=DSMARKET_BLUE, linewidth=2, label='Predicción media')
ax.plot(fechas_fut, p90_futuro.sum(axis=0), color=DSMARKET_GOLD, linewidth=1.5, linestyle='--',
        label='Percentil 90 (stock objetivo)')
ax.fill_between(fechas_fut, pred_futuro.sum(axis=0), p90_futuro.sum(axis=0), color=DSMARKET_GOLD, alpha=0.15)
ax.axvline(fechas_[-1], color='#52514e', linestyle=':', linewidth=1.2)
ax.set_title('Próximas 4 semanas con el modelo final: predicción central y percentil 90',
             color=DSMARKET_NAVY, fontweight='bold')
ax.set_ylabel('Unidades / día'); ax.legend(frameon=False)
plt.tight_layout(); plt.show()

for nombre, matriz in [('predicciones_28dias.csv', pred_futuro), ('predicciones_28dias_p90.csv', p90_futuro)]:
    salida = pd.DataFrame(matriz, columns=[f'F{i+1}' for i in range(28)])
    salida.insert(0, 'id', meta_['id'].values)
    salida.to_csv(nombre, index=False, float_format='%.4f')
    print(f"{nombre}: {salida.shape} | total 28 días: {matriz.sum():,.0f} unidades")
"""

MD_04_INTRO = """
## Actualización: los grupos de producto de la Tarea 2

> **Nota (octubre 2026).** La Tarea 2 se rehízo y ahora tiene **6 grupos de producto** elegidos con el método del codo. Las secciones anteriores de este notebook usan los 5 arquetipos de la versión anterior. Esta sección repite el cruce de la sección 3 (grupo de producto frente a la clase XYZ) con los grupos actuales. Es autocontenida: lee los CSV originales.
"""


def cargar(ruta):
    return nbformat.read(ruta, as_version=4)


def ejecutar_nuevas(nb, n_previas, preambulo):
    """Ejecuta solo las celdas añadidas (desde n_previas), con un preámbulo de imports y paleta."""
    tmp = nbformat.v4.new_notebook()
    tmp.cells = [nbformat.v4.new_code_cell(preambulo)] + [copy.deepcopy(c) for c in nb.cells[n_previas:]]
    tmp.metadata = nb.metadata
    NotebookClient(tmp, timeout=7200, kernel_name='python3', resources={'metadata': {'path': '.'}}).execute()
    for i, c in enumerate(tmp.cells[1:]):
        nb.cells[n_previas + i] = c
    return nb


PREAMBULO = """
import numpy as np, pandas as pd, matplotlib.pyplot as plt, warnings
from IPython.display import display
warnings.filterwarnings('ignore')
DSMARKET_NAVY = "#0a2a5c"; DSMARKET_BLUE = "#2a78d6"; DSMARKET_GOLD = "#eda100"; DSMARKET_GREEN = "#6a9f1f"
%matplotlib inline
"""

if __name__ == '__main__':
    textos = {}
    exec(open('textos_actualizacion.py', encoding='utf-8').read())

    # ---------- 03 ----------
    nb = cargar('03_original.ipynb')
    nb.cells.insert(1, nbformat.v4.new_markdown_cell(NOTA_03.strip()))
    n = len(nb.cells)
    for tipo, src in [('md', MD_03_INTRO), ('code', CODE_03_A), ('code', CODE_03_B), ('md', textos['HALLAZGO_03']),
                      ('md', MD_03_GRUPOS), ('code', CODE_03_C), ('md', textos['HALLAZGO_03_GRUPOS']),
                      # sección 16: revisión tras la tutoría
                      ('md', textos['MD_16_INTRO']),
                      ('md', textos['MD_16_1']),
                      ('md', textos['MD_16_2']), ('code', CODE_16_A), ('md', textos['HALLAZGO_16_2']),
                      ('md', textos['MD_16_3']), ('code', CODE_16_B), ('md', textos['HALLAZGO_16_3']),
                      ('code', CODE_16_C), ('md', textos['HALLAZGO_16_3_GRUPOS']),
                      ('md', textos['MD_16_4']), ('code', CODE_16_D), ('code', CODE_16_E),
                      ('md', textos['HALLAZGO_16_4']), ('code', CODE_16_F), ('md', textos['HALLAZGO_16_4_DIC']),
                      ('md', textos['MD_16_5']), ('code', CODE_16_G), ('md', textos['HALLAZGO_16_5']),
                      ('code', CODE_16_H), ('md', textos['HALLAZGO_16_5_DIC']),
                      ('md', textos['MD_16_7']), ('code', CODE_16_I), ('md', textos['HALLAZGO_16_7']),
                      ('code', CODE_16_J), ('md', textos['HALLAZGO_16_7_ENTREGA']),
                      ('md', textos['MD_16_8'])]:
        nb.cells.append(nbformat.v4.new_markdown_cell(src.strip()) if tipo == 'md' else nbformat.v4.new_code_cell(src.strip()))
    nb = ejecutar_nuevas(nb, n, PREAMBULO)
    nbformat.write(nb, '03_Forecasting_DSMarket.ipynb')
    print('03 actualizado')
