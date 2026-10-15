import numpy as np, pandas as pd
DATA_DIR = "data_dsmarket/data_dsmarket"
ventas = pd.read_csv(f"{DATA_DIR}/item_sales.csv")
dias = [c for c in ventas.columns if c.startswith('d_')]
V4 = ventas[dias].to_numpy(dtype=np.int16)
grupos = pd.read_csv("cache_forecast/segmentacion_productos.csv", index_col=0)
nombre_grupo = ventas['item'].map(grupos['nombre_grupo']).to_numpy()

# misma ventana y misma regla XYZ que en la sección 3 (últimos 90 días antes del fold 3, CV <= 1 / <= 2)
s4 = V4.shape[1] - 28
h90 = V4[:, s4-90:s4].astype(np.float64)
mu, sd = h90.mean(axis=1), h90.std(axis=1)
cv4 = np.where(mu > 0, sd / np.maximum(mu, 1e-9), 99.0)
xyz4 = np.where(cv4 <= 1.0, 'X', np.where(cv4 <= 2.0, 'Y', 'Z'))

cruce_nuevo = pd.crosstab(pd.Series(nombre_grupo, name='grupo de producto (Tarea 2)'),
                          pd.Series(xyz4, name='XYZ'), normalize='index') * 100
cruce_nuevo['series'] = pd.Series(nombre_grupo).value_counts()
cruce_nuevo.sort_values('X', ascending=False).round(1)
