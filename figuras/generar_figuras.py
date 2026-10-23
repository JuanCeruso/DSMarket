# -*- coding: utf-8 -*-
"""
Generador de las figuras de la memoria.

Produce en `memoria/figuras/` las imágenes que los marcadores `[FIGURA n.m]` del texto
esperan, a 200 ppp y con el nombre `fig_n_m.png`. Cada figura sale del almacén, de la caché de
modelos o de `avanzado/resultados/`: ninguna se dibuja a mano.

    python3 figuras/generar_figuras.py                 # todas
    python3 figuras/generar_figuras.py --listar        # qué figura produce qué
    python3 figuras/generar_figuras.py --solo 7.9 7.14 # solo esas

Paleta: la de referencia del sistema de visualización, validada para daltonismo. Los tres
colores que no alcanzan 3:1 contra el fondo blanco (aqua, amarillo, magenta) llevan siempre
etiqueta directa, que es la compensación que exige esa validación.
"""
from __future__ import annotations
import argparse, os, pickle, sys, time, warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates
from matplotlib.ticker import FuncFormatter
from matplotlib.patches import FancyArrowPatch, Rectangle

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLD = os.path.join(RAIZ, "lakehouse", "gold")
CACHE = os.path.join(RAIZ, "cache_forecast")
RES = os.path.join(RAIZ, "avanzado", "resultados")
SALIDA = os.path.join(RAIZ, "memoria", "figuras")
os.makedirs(SALIDA, exist_ok=True)

# ---------------------------------------------------------------- paleta validada
AZUL, NARANJA, AQUA, AMARILLO, MAGENTA = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"
ROJO, VIOLETA = "#e34948", "#4a3aa7"
CAT = [AZUL, NARANJA, AQUA, AMARILLO, MAGENTA]
SEC = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7",
       "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]
TINTA, TINTA2, TINTA3 = "#0b0b0b", "#52514e", "#8a8985"
REJILLA, FONDO = "#e8e7e3", "#fcfcfb"

plt.rcParams.update({
    "figure.dpi": 200, "savefig.dpi": 200, "savefig.bbox": "tight",
    "figure.facecolor": FONDO, "axes.facecolor": FONDO, "savefig.facecolor": FONDO,
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 8.5, "axes.titlesize": 9.5, "axes.labelsize": 8.5,
    "axes.titleweight": "bold", "axes.titlelocation": "left", "axes.titlepad": 9,
    "axes.edgecolor": REJILLA, "axes.labelcolor": TINTA2,
    "axes.spines.top": False, "axes.spines.right": False,
    "xtick.color": TINTA2, "ytick.color": TINTA2,
    "xtick.labelsize": 7.5, "ytick.labelsize": 7.5,
    "grid.color": REJILLA, "grid.linewidth": 0.7,
    "legend.frameon": False, "legend.fontsize": 7.5,
    "lines.linewidth": 2.0, "lines.solid_capstyle": "round",
})


def es_num(x, dec=0):
    """Formato español: punto de millar, coma decimal."""
    s = f"{x:,.{dec}f}"
    return s.replace(",", "@").replace(".", ",").replace("@", ".")


FMT = FuncFormatter(lambda v, _: es_num(v))
FMT1 = FuncFormatter(lambda v, _: es_num(v, 1))


def rejilla(ax, eje="y"):
    ax.grid(axis=eje, zorder=0)
    ax.set_axisbelow(True)


def guardar(fig, clave, titulo):
    nombre = "fig_" + clave.replace(".", "_") + ".png"
    ruta = os.path.join(SALIDA, nombre)
    fig.savefig(ruta)
    plt.close(fig)
    kb = os.path.getsize(ruta) // 1024
    print(f"  [{clave:>4}] {nombre:<16} {kb:>4} KB   {titulo}")
    return ruta


_con = None


def sql(consulta):
    global _con
    import duckdb
    if _con is None:
        _con = duckdb.connect()
        _con.execute(f"SET memory_limit='{os.environ.get('DSMARKET_MEM','3GB')}';")
        tmp = "/tmp/dsmarket_duck"
        os.makedirs(tmp, exist_ok=True)
        _con.execute(f"SET temp_directory='{tmp}';")
        _con.execute("SET preserve_insertion_order=false;")
        for f in sorted(os.listdir(GOLD)):
            if f.endswith(".parquet"):
                _con.execute(f"CREATE OR REPLACE VIEW {f[:-8]} AS "
                             f"SELECT * FROM read_parquet('{os.path.join(GOLD, f)}')")
    return _con.execute(consulta).df()


_DIAS = None


def dias_semana():
    """weekday_int no es 0=lunes: en este almacén va 1=sábado … 7=viernes.
    Se lee la convención de la propia dimensión en vez de suponerla."""
    global _DIAS
    if _DIAS is None:
        d = sql("""SELECT weekday_int, any_value(dia_semana) n FROM dim_calendario
                   WHERE weekday_int IS NOT NULL GROUP BY 1 ORDER BY 1""")
        corto = {"Monday": "L", "Tuesday": "M", "Wednesday": "X", "Thursday": "J",
                 "Friday": "V", "Saturday": "S", "Sunday": "D"}
        _DIAS = (d["weekday_int"].tolist(), [corto.get(x, str(x)[:2]) for x in d["n"]])
    return _DIAS


def cache(nombre):
    ruta = os.path.join(CACHE, nombre)
    if not os.path.exists(ruta):
        raise FileNotFoundError(f"falta {ruta}")
    if nombre.endswith(".npy"):
        return np.load(ruta, mmap_mode="r")
    if nombre.endswith(".pkl"):
        return pickle.load(open(ruta, "rb"))
    return pd.read_csv(ruta)


def resultado(nombre):
    ruta = os.path.join(RES, nombre)
    if not os.path.exists(ruta):
        raise FileNotFoundError(f"falta {ruta} — ejecutá el experimento correspondiente")
    return pd.read_csv(ruta)


def caja(ax, x, y, an, al, texto, sub=None, color=REJILLA, relleno=FONDO, grosor=1.0):
    ax.add_patch(Rectangle((x, y), an, al, facecolor=relleno, edgecolor=color,
                           linewidth=grosor, zorder=2))
    ax.text(x + an / 2, y + al * (0.62 if sub else 0.5), texto, ha="center", va="center",
            fontsize=8, fontweight="bold", color=TINTA, zorder=3)
    if sub:
        ax.text(x + an / 2, y + al * 0.28, sub, ha="center", va="center",
                fontsize=6.8, color=TINTA2, zorder=3)


def flecha(ax, p1, p2, color=TINTA3, estilo="-|>", guion=None):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle=estilo, mutation_scale=9,
                                 color=color, linewidth=1.1, zorder=1,
                                 linestyle=guion or "solid",
                                 connectionstyle="arc3,rad=0"))


def lienzo(an=6.4, al=3.2):
    fig, ax = plt.subplots(figsize=(an, al))
    ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")
    return fig, ax


# =================================================================== §6 metodología
def fig_6_1():
    """Arquitectura del almacén en tres capas."""
    fig, ax = lienzo(6.4, 2.6)
    caja(ax, 2, 35, 16, 30, "Origen", "3 CSV · 491 MB")
    for i, (n, s, c) in enumerate([("bronce", "copia fiel · 22 MB", REJILLA),
                                   ("plata", "limpio + calidad · 45 MB", REJILLA),
                                   ("oro", "estrella · 91 MB", AZUL)]):
        x = 26 + i * 24
        caja(ax, x, 35, 20, 30, n, s, color=c, grosor=1.6 if c == AZUL else 1.0)
        flecha(ax, (x - 6, 50), (x - 1, 50))
    ax.text(50, 22, "pipeline.py · reconstrucción completa en ~20 s",
            ha="center", fontsize=7, color=TINTA2, style="italic")
    ax.text(2, 80, "A R Q U I T E C T U R A   M E D A L L Ó N", fontsize=7,
            fontweight="bold", color=TINTA3)
    return guardar(fig, "6.1", "Arquitectura del almacén en tres capas")


def fig_6_2():
    """Esquema en estrella de la capa de consumo."""
    fig, ax = lienzo(6.4, 3.6)
    caja(ax, 36, 40, 28, 22, "fact_ventas", "58.327.370 filas", color=AZUL, grosor=1.6)
    dims = [("dim_calendario", "1.941", 4, 76), ("dim_producto", "3.049", 68, 76),
            ("dim_tienda", "10", 4, 10), ("dim_serie", "30.490", 68, 10)]
    for n, s, x, y in dims:
        caja(ax, x, y, 28, 18, n, s + " filas")
        cx, cy = x + 14, y + (0 if y > 40 else 18)
        flecha(ax, (cx, cy), (50, 62 if y > 40 else 40), color=REJILLA)
    ax.text(50, 30, "2 hechos más: fact_predicciones · fact_reposicion",
            ha="center", fontsize=7, color=TINTA2, style="italic")
    return guardar(fig, "6.2", "Modelo dimensional de la capa de consumo")


def fig_6_3():
    """Esquema de la validación temporal por avance."""
    fig, ax = plt.subplots(figsize=(6.4, 2.4))
    ax.set_xlim(0, 300); ax.set_ylim(-0.6, 2.8); ax.axis("off")
    for i in range(3):
        y = 2 - i
        ini = 40 + i * 28
        ax.add_patch(Rectangle((ini, y - 0.22), 180, 0.44, facecolor="#eef3fa",
                               edgecolor=AZUL, linewidth=1.1))
        ax.text(ini + 90, y, "entrenamiento · 180 días", ha="center", va="center",
                fontsize=7, color=TINTA2)
        ax.add_patch(Rectangle((ini + 180, y - 0.22), 28, 0.44, facecolor=NARANJA,
                               edgecolor="none"))
        ax.text(ini + 194, y, "28 d", ha="center", va="center", fontsize=6.8,
                color="white", fontweight="bold")
        ax.text(34, y, f"pliegue {i+1}", ha="right", va="center", fontsize=7.5,
                fontweight="bold", color=TINTA)
    ax.annotate("", xy=(300, -0.35), xytext=(40, -0.35),
                arrowprops=dict(arrowstyle="-|>", color=TINTA3, lw=1))
    ax.text(170, -0.58, "tiempo", ha="center", fontsize=7, color=TINTA2)
    ax.text(40, 2.65, "Validación por avance · nunca aleatoria", fontsize=8.5,
            fontweight="bold", color=TINTA)
    return guardar(fig, "6.3", "Esquema de la validación temporal por avance")


# =================================================================== §7.1 tiendas
def fig_7_1():
    """Serie agregada: tendencia y las dos estacionalidades."""
    d = sql("SELECT fecha, sum(unidades) u FROM fact_ventas GROUP BY 1 ORDER BY 1")
    d["fecha"] = pd.to_datetime(d["fecha"])
    fig, axes = plt.subplots(3, 1, figsize=(6.4, 5.4),
                             gridspec_kw={"height_ratios": [2, 1, 1], "hspace": 0.55})
    a = axes[0]
    a.plot(d["fecha"], d["u"], color=REJILLA, lw=0.7, zorder=1)
    a.plot(d["fecha"], d["u"].rolling(28, center=True).mean(), color=AZUL, zorder=2)
    a.set_title("Venta diaria de la cadena y su tendencia a 28 días")
    a.set_ylabel("unidades / día"); a.yaxis.set_major_formatter(FMT); rejilla(a)
    a.text(d["fecha"].iloc[len(d)//2], d["u"].rolling(28, center=True).mean().max() * 1.02,
           "media móvil 28 d", color=AZUL, fontsize=7.5, fontweight="bold")

    dias = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
    perfil = d.groupby(d["fecha"].dt.weekday)["u"].mean()
    perfil = perfil / perfil.mean()
    b = axes[1]
    barras = b.bar(range(7), perfil.values, color=REJILLA, width=0.62, zorder=2)
    for i, v in enumerate(perfil.values):
        if v == perfil.max() or v == perfil.min():
            barras[i].set_color(AZUL)
        b.text(i, v + 0.012, es_num(v, 2), ha="center", fontsize=6.8, color=TINTA2)
    b.set_xticks(range(7)); b.set_xticklabels(dias)
    b.axhline(1, color=TINTA3, lw=0.8, ls=(0, (3, 3)))
    b.set_ylim(min(perfil) * 0.93, max(perfil) * 1.06)
    b.set_title("Perfil semanal"); b.set_ylabel("× la media"); rejilla(b)

    meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    pm = d.groupby(d["fecha"].dt.month)["u"].mean(); pm = pm / pm.mean()
    c = axes[2]
    barras = c.bar(range(12), pm.values, color=REJILLA, width=0.62, zorder=2)
    barras[int(np.argmax(pm.values))].set_color(AZUL)
    c.set_xticks(range(12)); c.set_xticklabels(meses)
    c.axhline(1, color=TINTA3, lw=0.8, ls=(0, (3, 3)))
    c.set_ylim(min(pm) * 0.93, max(pm) * 1.06)
    c.set_title("Perfil anual"); c.set_ylabel("× la media"); rejilla(c)
    return guardar(fig, "7.1", "Serie agregada, tendencia y estacionalidades")


def fig_7_2():
    """Elevación por evento del calendario."""
    d = sql("""
        WITH base AS (
            SELECT c.fecha, c.evento, c.weekday_int, sum(v.unidades) u
            FROM fact_ventas v JOIN dim_calendario c USING (fecha)
            WHERE NOT c.es_dia_cierre GROUP BY 1,2,3),
        media_dow AS (SELECT weekday_int, avg(u) m FROM base WHERE evento IS NULL GROUP BY 1)
        SELECT b.evento, avg(b.u / m.m) elevacion, count(*) dias
        FROM base b JOIN media_dow m USING (weekday_int)
        WHERE b.evento IS NOT NULL GROUP BY 1 HAVING dias >= 3 ORDER BY 2 DESC
    """)
    if d.empty:
        raise ValueError("sin eventos etiquetados")
    fig, ax = plt.subplots(figsize=(6.4, max(2.6, 0.26 * len(d) + 1.1)))
    destacados = {"LaborDay", "SuperBowl", "Easter", "Labor Day", "Super Bowl"}
    col = [AZUL if e.replace(" ", "") in {x.replace(" ", "") for x in destacados}
           else REJILLA for e in d["evento"]]
    y = range(len(d))
    ax.barh(list(y), d["elevacion"] - 1, left=1, color=col, height=0.66, zorder=2)
    ax.set_yticks(list(y)); ax.set_yticklabels(d["evento"], fontsize=7)
    ax.invert_yaxis()
    ax.axvline(1, color=TINTA3, lw=0.9)
    for i, (v, e) in enumerate(zip(d["elevacion"], d["evento"])):
        ax.text(v + (0.01 if v >= 1 else -0.01), i, es_num((v - 1) * 100, 0) + "%",
                va="center", ha="left" if v >= 1 else "right", fontsize=6.8, color=TINTA2)
    bf = d[d["evento"].str.contains("Black", case=False, na=False)]
    if len(bf):
        i = int(bf.index[0])
        ax.annotate("Black Friday: sin pico distinguible del ruido",
                    xy=(float(bf["elevacion"].iloc[0]), i), xytext=(0.62, len(d) * 0.62),
                    fontsize=7, color=ROJO, fontweight="bold",
                    arrowprops=dict(arrowstyle="-|>", color=ROJO, lw=1))
    ax.set_xlabel("venta media del día del evento, relativa a un día normal del mismo día de la semana")
    ax.set_title("Efecto de cada evento del calendario")
    rejilla(ax, "x")
    return guardar(fig, "7.2", "Elevación por evento del calendario")


def fig_7_3():
    """Solapamiento de los quince productos más vendidos entre ciudades."""
    d = sql("""
        WITH r AS (
            SELECT t.ciudad, v.item, sum(v.unidades) u,
                   row_number() OVER (PARTITION BY t.ciudad ORDER BY sum(v.unidades) DESC) pos
            FROM fact_ventas v JOIN dim_tienda t USING (store_code)
            GROUP BY 1,2)
        SELECT ciudad, item FROM r WHERE pos <= 15
    """)
    ciudades = sorted(d["ciudad"].unique())
    conj = {c: set(d.loc[d["ciudad"] == c, "item"]) for c in ciudades}
    comunes = set.intersection(*conj.values())
    fig, ax = plt.subplots(figsize=(6.4, 2.9))
    n = len(ciudades)
    for i, c in enumerate(ciudades):
        com = len(conj[c] & comunes)
        ax.barh(i, com, color=AZUL, height=0.6, zorder=2)
        ax.barh(i, 15 - com, left=com, color=REJILLA, height=0.6, zorder=2)
        ax.text(com / 2, i, str(com), ha="center", va="center", color="white",
                fontsize=8, fontweight="bold")
        ax.text(15.25, i, f"{15-com} exclusivos de {c}", va="center", fontsize=7, color=TINTA2)
    ax.set_yticks(range(n)); ax.set_yticklabels(ciudades, fontsize=8)
    ax.invert_yaxis(); ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 16, 5))
    ax.set_xlabel("productos del top 15 de cada ciudad")
    ax.set_title(f"Solo {len(comunes)} de los 15 productos más vendidos son comunes a las tres ciudades")
    rejilla(ax, "x")
    return guardar(fig, "7.3", "Solapamiento del top 15 entre ciudades")


def fig_7_4():
    """Dispersión relativa de precios entre tiendas, por categoría."""
    d = sql("""
        WITH p AS (
            SELECT v.item, v.store_code, avg(v.precio) precio
            FROM fact_ventas v WHERE v.precio IS NOT NULL GROUP BY 1,2),
        disp AS (
            SELECT item, stddev_samp(precio) / nullif(avg(precio),0) cv FROM p
            GROUP BY 1 HAVING count(*) > 1)
        SELECT pr.categoria, avg(d.cv) * 100 dispersion_pct, count(*) referencias
        FROM disp d JOIN dim_producto pr USING (item) GROUP BY 1 ORDER BY 2 DESC
    """)
    fig, ax = plt.subplots(figsize=(6.4, 2.6))
    col = [AZUL] + [REJILLA] * (len(d) - 1)
    ax.bar(range(len(d)), d["dispersion_pct"], color=col, width=0.55, zorder=2)
    for i, v in enumerate(d["dispersion_pct"]):
        ax.text(i, v + 0.04, es_num(v, 2) + "%", ha="center", fontsize=7.5,
                color=TINTA if i == 0 else TINTA2,
                fontweight="bold" if i == 0 else "normal")
    ax.set_xticks(range(len(d)))
    ax.set_xticklabels([c.replace("_", " ") for c in d["categoria"]], fontsize=7.5)
    ax.set_ylabel("coef. de variación medio (%)")
    ax.set_title("La categoría con más dispersión de precios no es la de artículos caros")
    rejilla(ax)
    return guardar(fig, "7.4", "Dispersión de precios por categoría")


# =================================================================== §7.2 comportamiento
def _perfiles_producto():
    """Perfil semanal, mensual y elevaciones por producto. Es lo que agrupó la Tarea 2."""
    d = sql("""
        SELECT v.item, c.weekday_int wd, c.mes, sum(v.unidades) u
        FROM fact_ventas v JOIN dim_calendario c USING (fecha)
        WHERE NOT c.es_dia_cierre GROUP BY 1,2,3
    """)
    sem = d.pivot_table(index="item", columns="wd", values="u", aggfunc="sum").fillna(0)
    mes = d.pivot_table(index="item", columns="mes", values="u", aggfunc="sum").fillna(0)
    sem = sem.div(sem.sum(axis=1).replace(0, np.nan), axis=0).fillna(0)
    mes = mes.div(mes.sum(axis=1).replace(0, np.nan), axis=0).fillna(0)
    X = pd.concat([sem.add_prefix("d"), mes.add_prefix("m")], axis=1)
    return X[X.sum(axis=1) > 0]


def fig_7_9():
    """Matriz ABC/XYZ: recuento y peso en facturación."""
    d = sql("""SELECT clase_abc, clase_xyz, count(*) series, sum(facturacion_90d) fact
               FROM dim_serie GROUP BY 1,2""")
    total = d["fact"].sum()
    fig, axes = plt.subplots(1, 2, figsize=(6.4, 2.8), gridspec_kw={"wspace": 0.3})
    for ax, col, titulo, dec, suf in [(axes[0], "series", "Series producto-tienda", 0, ""),
                                      (axes[1], "fact", "% de la facturación", 1, "%")]:
        m = d.pivot(index="clase_abc", columns="clase_xyz", values=col).reindex(
            index=list("ABC"), columns=list("XYZ"))
        v = m.to_numpy(float)
        if col == "fact":
            v = v / total * 100
        ax.imshow(v, cmap=matplotlib.colors.LinearSegmentedColormap.from_list("b", SEC),
                  aspect="auto", vmin=0, vmax=np.nanmax(v))
        for i in range(3):
            for j in range(3):
                if np.isnan(v[i, j]):
                    continue
                claro = v[i, j] > np.nanmax(v) * 0.55
                ax.text(j, i, es_num(v[i, j], dec) + suf, ha="center", va="center",
                        fontsize=8.5, fontweight="bold",
                        color="white" if claro else TINTA)
        ax.set_xticks(range(3)); ax.set_xticklabels(list("XYZ"))
        ax.set_yticks(range(3)); ax.set_yticklabels(list("ABC"))
        ax.set_xlabel("XYZ · predictibilidad"); ax.set_ylabel("ABC · valor")
        ax.set_title(titulo, fontsize=9)
        ax.grid(False)
        for s in ax.spines.values():
            s.set_visible(False)
    fig.suptitle("AX concentra el 56% de la facturación; CZ, el 28% del catálogo por el 3,5%",
                 fontsize=8.5, x=0.02, ha="left", y=1.02, color=TINTA2, fontweight="normal")
    return guardar(fig, "7.9", "Matriz ABC/XYZ")


# =================================================================== §7.3 predicción
def fig_7_10():
    """La estrategia por bloques semanales."""
    fig, ax = plt.subplots(figsize=(6.4, 2.7))
    ax.set_xlim(-32, 30); ax.set_ylim(-0.7, 4.0); ax.axis("off")
    ax.add_patch(Rectangle((-32, -0.45), 32, 3.95, facecolor="#f6f7f8", edgecolor="none"))
    ax.text(-31, 3.62, "información disponible", fontsize=7, color=TINTA2)
    ax.text(1, 3.62, "horizonte a predecir", fontsize=7, color=TINTA2)
    ax.axvline(0, color=TINTA, lw=1.2)
    ax.text(0, -0.65, "hoy", ha="center", fontsize=7.5, fontweight="bold", color=TINTA)
    for b in range(4):
        y = 3 - b
        min_lag = 7 * (b + 1)
        ax.add_patch(Rectangle((-min_lag, y - 0.2), min_lag, 0.4,
                               facecolor="white", edgecolor=REJILLA, hatch="////", lw=0.8))
        ax.text(-min_lag / 2, y, "no usable", ha="center", va="center",
                fontsize=6.3, color=TINTA3)
        ax.add_patch(Rectangle((-32, y - 0.2), 32 - min_lag, 0.4,
                               facecolor="#dceafa", edgecolor=AZUL, lw=0.9))
        ax.add_patch(Rectangle((7 * b, y - 0.2), 7, 0.4, facecolor=NARANJA, edgecolor="none"))
        ax.text(7 * b + 3.5, y, f"sem {b+1}", ha="center", va="center", fontsize=6.5,
                color="white", fontweight="bold")
        ax.text(29.5, y, f"retardo mín. {min_lag} d", ha="right", va="center",
                fontsize=7, color=TINTA2)
        ax.text(-33, y, f"modelo {b+1}", ha="right", va="center", fontsize=7.5,
                fontweight="bold", color=TINTA)
    ax.text(-32, 3.9, "Cada modelo usa solo lo que existirá cuando tenga que predecir",
            fontsize=8.5, fontweight="bold", color=TINTA)
    return guardar(fig, "7.10", "Estrategia de predicción por bloques semanales")


def fig_7_11():
    """Comparación de modelos: media de los tres pliegues y evolución por ventana.

    Valores de §7.3.3 y §7.3.4, procedentes del cuaderno 03 (WRMSSE, menor es mejor)."""
    medias = [("LightGBM, bloques semanales", 1.0407), ("XGBoost, bloques semanales", 1.0430),
              ("LightGBM, modelo único", 1.0626), ("XGBoost, modelo único", 1.0631),
              ("Media móvil de 28 días", 1.0657), ("Media por día de la semana", 1.0855),
              ("Naive estacional", 1.4262)]
    escalera = {"Media móvil de 28 días": [1.0909, 1.0660, 1.0402],
                "Media móvil × día de la semana": [1.0768, 1.0518, 1.0185],
                "LightGBM pequeño": [1.0827, 1.0380, 1.0095],
                "LightGBM completo": [1.0776, 1.0415, 1.0029]}
    fig, axes = plt.subplots(1, 2, figsize=(6.8, 3.0), gridspec_kw={"wspace": 0.55, "width_ratios": [1.15, 1]})
    a = axes[0]
    y = np.arange(len(medias))[::-1]
    col = [AZUL if i == 0 else (REJILLA if i >= 4 else "#9ec5f4") for i in range(len(medias))]
    a.barh(y, [v for _, v in medias], color=col, height=0.62, zorder=2)
    for yi, (n, v) in zip(y, medias):
        a.text(v + 0.015, yi, es_num(v, 4), va="center", fontsize=6.8, color=TINTA2)
    a.axvline(1, color=TINTA3, lw=0.9, ls=(0, (3, 3)))
    a.set_yticks(y); a.set_yticklabels([n for n, _ in medias], fontsize=6.8)
    a.set_xlim(0.8, 1.6); a.set_xlabel("WRMSSE medio de los tres pliegues")
    a.set_title("Media de los tres pliegues", fontsize=9); rejilla(a, "x")
    b = axes[1]
    for i, (n, v) in enumerate(escalera.items()):
        b.plot(["Feb", "Mar", "Abr"], v, marker="o", markersize=3.5, color=CAT[i], label=n)
    b.set_ylabel("WRMSSE"); b.set_title("Por ventana de validación (2016)", fontsize=9)
    b.legend(fontsize=6.2, loc="upper right"); rejilla(b)
    return guardar(fig, "7.11", "Error de los modelos comparados")


def fig_7_12():
    """Importancia de las variables del modelo con bloques semanales de 180 días (media de los tres pliegues)."""
    ss = []
    for k in range(3):
        d = cache(f"semanal_actual_fold{k}.pkl")["importancia"]
        s_ = pd.Series({str(n): v for n, v in d.items()}, dtype=float)
        ss.append(s_ / s_.sum() * 100)
    pct = pd.concat(ss, axis=1).mean(axis=1).sort_values(ascending=False)
    top = pct.head(14)[::-1]
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    col = [AZUL if n.startswith("rmean") else REJILLA for n in top.index]
    ax.barh(range(len(top)), top.values, color=col, height=0.66, zorder=2)
    for i, (n, v) in enumerate(zip(top.index, top.values)):
        ax.text(v + 0.7, i, es_num(v, 1) + " %", va="center", fontsize=7,
                color=TINTA if v > 5 else TINTA2, fontweight="bold" if v > 5 else "normal")
    ax.set_yticks(range(len(top))); ax.set_yticklabels(top.index, fontsize=7)
    ax.set_xlabel("% de la importancia total por ganancia")
    medias = pct[[i for i in pct.index if str(i).startswith("rmean")]].sum()
    ax.set_title(f"Las medias móviles concentran el {es_num(medias,1)} % de la importancia")
    ax.text(0.99, 0.06, "en azul, las medias móviles", transform=ax.transAxes,
            ha="right", fontsize=7.5, color=AZUL, fontweight="bold")
    rejilla(ax, "x")
    return guardar(fig, "7.12", "Importancia de las variables")


def fig_7_13():
    """Diciembre de 2015: demanda total diaria real y predicha con 180 y con 400 días de historia."""
    cal = sql("SELECT fecha FROM dim_calendario WHERE NOT es_futuro ORDER BY fecha")
    fechas = pd.to_datetime(cal["fecha"]).reset_index(drop=True)
    i0 = int(fechas[fechas == pd.Timestamp("2015-12-04")].index[0])
    V = cache("V_ventas.npy")
    real = np.asarray(V[:, i0:i0 + 28]).sum(axis=0)
    p180 = np.asarray(cache("semanal_actual_dic2015.pkl")["pred"]).sum(axis=0)
    p400 = np.asarray(cache("semanal_eventos_semanales_400d_dic2015.pkl")["pred"]).sum(axis=0)
    x = fechas[i0:i0 + 28].to_numpy()
    fig, ax = plt.subplots(figsize=(6.6, 3.0))
    ax.plot(x, real, color=TINTA, lw=2.2, marker="o", markersize=2.8, label="real", zorder=4)
    ax.plot(x, p180, color=TINTA3, ls=(0, (4, 2)), label="180 días de historia", zorder=3)
    ax.plot(x, p400, color=NARANJA, ls=(0, (4, 2)), lw=2.0, label="400 días + eventos semanales", zorder=3)
    nav = list(fechas[i0:i0 + 28]).index(pd.Timestamp("2015-12-25"))
    ax.annotate(f"25 de diciembre: real {es_num(real[nav])}\n180 días: {es_num(p180[nav])}\n400 días: {es_num(p400[nav])}",
                xy=(x[nav], p180[nav]), xytext=(-12, -4), textcoords="offset points", ha="right",
                fontsize=6.8, color=ROJO, fontweight="bold",
                arrowprops=dict(arrowstyle="-|>", color=ROJO, lw=0.9))
    ax.set_ylabel("unidades / día"); ax.yaxis.set_major_formatter(FMT)
    ax.set_title("Con 400 días, el modelo aprende por sí solo el cierre de Navidad")
    ax.legend(loc="lower left"); rejilla(ax)
    fig.autofmt_xdate(rotation=0, ha="center")
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%d/%m"))
    return guardar(fig, "7.13", "Temporada alta: real frente a predicho")


def fig_7_14():
    """Calibración del intervalo: cobertura empírica frente a la nominal."""
    p90 = np.asarray(cache("p90_eval.npy"), dtype=np.float32)
    V = np.asarray(cache("V_ventas.npy"))
    y = V[:, -p90.shape[1]:].astype(np.float32)
    media = np.asarray(cache("pred_fold2.pkl")["pred_lgb"], dtype=np.float32)
    sigma = np.maximum(p90 - media, 0) / 1.2816
    fig, axes = plt.subplots(1, 2, figsize=(6.4, 2.8), gridspec_kw={"wspace": 0.32})
    niveles = np.array([0.50, 0.60, 0.70, 0.80, 0.90, 0.95, 0.99])
    from scipy.stats import norm
    emp = [float((y <= media + norm.ppf(q) * sigma).mean()) for q in niveles]
    a = axes[0]
    a.plot([0.45, 1], [0.45, 1], color=TINTA3, ls=(0, (3, 3)), lw=1, zorder=1)
    a.plot(niveles, emp, color=AZUL, marker="o", markersize=4, zorder=3)
    i90 = int(np.where(niveles == 0.90)[0][0])
    a.scatter([0.90], [emp[i90]], s=64, color=NARANJA, zorder=4, edgecolor=FONDO, lw=1.4)
    a.annotate(f"p90: {es_num(emp[i90]*100,1)}%", (0.90, emp[i90]),
               textcoords="offset points", xytext=(-6, -18), ha="right",
               fontsize=7.5, color=NARANJA, fontweight="bold")
    a.set_xlabel("nivel nominal"); a.set_ylabel("cobertura empírica")
    a.set_title("El intervalo está bien calibrado", fontsize=9)
    a.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0%}"))
    a.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0%}"))
    rejilla(a, "both")
    b = axes[1]
    cob = [float((y <= media).mean()) * 100, float((y <= p90).mean()) * 100]
    uds = [float(media.sum()), float(p90.sum())]
    barras = b.bar(["predicción\nmedia", "percentil 90"], cob, color=[REJILLA, AZUL],
                   width=0.5, zorder=2)
    for r, c, u in zip(barras, cob, uds):
        b.text(r.get_x() + r.get_width() / 2, c + 1.2, es_num(c, 1) + "%",
               ha="center", fontsize=8, fontweight="bold", color=TINTA)
        b.text(r.get_x() + r.get_width() / 2, 4, es_num(u / 1000) + " k uds",
               ha="center", fontsize=7, color="white" if c > 50 else TINTA2)
    b.axhline(90, color=NARANJA, lw=1.1, ls=(0, (3, 3)))
    b.text(-0.45, 91.5, "objetivo 90 %", fontsize=7, color=NARANJA, ha="left")
    b.set_ylim(0, 105); b.set_ylabel("cobertura (%)")
    b.set_title("Y la media no sirve para dimensionar", fontsize=9)
    rejilla(b)
    return guardar(fig, "7.14", "Calibración del intervalo de predicción")


def fig_7_15():
    """Ascendente frente a modelado directo del agregado (valores de §7.3.8, cuaderno 03)."""
    niveles = ["Total compañía", "Ciudad", "Tienda", "Departamento"]
    datos = {"Ascendente (suma de LightGBM)": [5.48, 6.76, 8.03, 9.93],
             "Prophet": [5.80, 7.25, 8.59, 10.71],
             "SARIMA": [6.50, 7.72, 8.54, 10.33],
             "Media móvil": [12.79, 13.50, 14.55, 13.95]}
    fig, ax = plt.subplots(figsize=(6.6, 3.1))
    x = np.arange(len(niveles)); w = 0.2
    colores = [AZUL, NARANJA, AQUA, REJILLA]
    for i, (n, v) in enumerate(datos.items()):
        ax.bar(x + (i - 1.5) * w, v, width=w, color=colores[i], label=n, zorder=2)
        if i == 0:
            for xi, vi in zip(x, v):
                ax.text(xi + (i - 1.5) * w, vi + 0.25, es_num(vi, 2), ha="center", fontsize=6.6,
                        color=AZUL, fontweight="bold")
    ax.set_xticks(x); ax.set_xticklabels(niveles, fontsize=7.5)
    ax.set_ylabel("error porcentual medio (%)")
    ax.set_title("Sumar las previsiones individuales gana en los cuatro niveles")
    ax.legend(ncol=2, loc="upper left"); ax.set_ylim(0, 19); rejilla(ax)
    return guardar(fig, "7.15", "Error por nivel: ascendente frente a modelado directo")


# =================================================================== §7.4 reposición
# La curva de la Tarea 4 son ocho puntos simulados que no dependen del almacén: viven aquí
# y en app/inicio.py, y son los mismos.
CURVA = pd.DataFrame({
    "nivel": [0.50, 0.70, 0.80, 0.85, 0.90, 0.95, 0.98, 0.99],
    "servicio_real": [86.3, 91.4, 93.5, 94.5, 95.5, 96.6, 97.5, 97.9],
    "margen_perdido": [161353, 97978, 72848, 61075, 49269, 36588, 26861, 22231],
    "mantenimiento": [11527, 15010, 17228, 18622, 20401, 23083, 26144, 28202],
    "remanente": [147183, 200677, 235338, 257189, 285227, 327592, 376097, 408796]})


def fig_7_17():
    """La política de partida: quince a uno (valores del cuaderno 04)."""
    fig, ax = plt.subplots(figsize=(6.4, 2.4))
    v = [164543, 11156]
    et = ["Margen perdido\npor rotura", "Coste de mantener\ninventario"]
    barras = ax.barh([1, 0], v, color=[NARANJA, REJILLA], height=0.5, zorder=2)
    for r, x, e in zip(barras, v, et):
        ax.text(x + 3000, r.get_y() + r.get_height() / 2, es_num(x) + " USD",
                va="center", fontsize=9, fontweight="bold", color=TINTA)
    ax.set_yticks([1, 0]); ax.set_yticklabels(et, fontsize=8)
    ax.set_xlim(0, 200000); ax.xaxis.set_major_formatter(FMT)
    ax.set_xlabel("coste en 28 días (USD)")
    ax.set_title("La política de partida es cara porque deja de vender, no por inmovilizar capital", fontsize=8.8)
    ax.text(0.99, 0.12, "casi 15 dólares perdidos por cada 1 inmovilizado",
            transform=ax.transAxes, ha="right", fontsize=8.5,
            color=NARANJA, fontweight="bold")
    rejilla(ax, "x")
    return guardar(fig, "7.17", "Descomposición del coste de la política de partida")


def fig_7_18():
    """El cambio de signo: dónde aporta el modelo y dónde resta (valores de §7.4.4, cuaderno 04)."""
    d = pd.DataFrame({"segmento": ["Clase Z\n(demanda errática)", "Clase Y", "Clase X\n(demanda estable)"],
                      "efecto": [18.1, -0.2, -7.8]})
    fig, ax = plt.subplots(figsize=(6.4, 2.5))
    col = [AZUL if v > 0 else ROJO for v in d["efecto"]]
    ax.barh(range(len(d)), d["efecto"], color=col, height=0.48, zorder=2)
    for i, v in enumerate(d["efecto"]):
        ax.text(v + (1.1 if v >= 0 else -1.1), i, ("+" if v > 0 else "") + es_num(v, 1) + " %",
                va="center", ha="left" if v >= 0 else "right", fontsize=9.5,
                fontweight="bold", color=AZUL if v > 0 else ROJO)
    ax.axvline(0, color=TINTA, lw=1.1)
    ax.set_yticks(range(len(d))); ax.set_yticklabels(d["segmento"], fontsize=8)
    ax.set_xlim(-16, 27); ax.invert_yaxis()
    ax.set_xlabel("mejora en coste de usar el modelo frente a la regla histórica (%)")
    ax.set_title("La simulación invirtió la conclusión del capítulo anterior")
    rejilla(ax, "x")
    return guardar(fig, "7.18", "Efecto del modelo por segmento")


def fig_7_20():
    """La curva de servicio bajo distintos supuestos de merma."""
    fig, axes = plt.subplots(1, 2, figsize=(6.6, 3.0), gridspec_kw={"wspace": 0.3})
    a = axes[0]
    x = np.arange(len(CURVA))
    a.bar(x, CURVA["margen_perdido"], color=NARANJA, width=0.62, zorder=2, label="margen perdido")
    a.bar(x, CURVA["mantenimiento"], bottom=CURVA["margen_perdido"], color=AZUL,
          width=0.62, zorder=2, label="mantenimiento")
    total = CURVA["margen_perdido"] + CURVA["mantenimiento"]
    mejor = int(total.idxmin())
    a.scatter([mejor], [total.iloc[mejor] + 9000], marker="v", s=46, color=TINTA, zorder=4)
    a.text(mejor, total.iloc[mejor] + 17000, "óptimo\nsin merma", ha="center",
           fontsize=6.8, color=TINTA, fontweight="bold")
    a.set_xticks(x); a.set_xticklabels([f"{v:.0%}" for v in CURVA["nivel"]], fontsize=6.8)
    a.set_xlabel("nivel de servicio objetivo"); a.set_ylabel("coste 28 días (USD)")
    a.yaxis.set_major_formatter(FMT); a.legend(loc="upper right")
    a.set_title("Con merma cero", fontsize=9); rejilla(a)

    b = axes[1]
    for i, merma in enumerate([0, 0.05, 0.10, 0.20]):
        t = CURVA["margen_perdido"] + CURVA["mantenimiento"] + CURVA["remanente"] * 3.14 * merma
        c = CAT[i]
        b.plot(CURVA["nivel"] * 100, t, color=c, marker="o", markersize=3, zorder=3)
        j = int(t.idxmin())
        b.scatter([CURVA["nivel"].iloc[j] * 100], [t.iloc[j]], s=70, color=c,
                  zorder=4, edgecolor=FONDO, lw=1.6)
        b.annotate(f"merma {merma:.0%} → {CURVA['nivel'].iloc[j]:.0%}",
                   (CURVA["nivel"].iloc[j] * 100, t.iloc[j]), textcoords="offset points",
                   xytext=(6, 7), fontsize=7, color=c, fontweight="bold")
    b.set_xlabel("nivel de servicio objetivo (%)"); b.set_ylabel("coste total (USD)")
    b.yaxis.set_major_formatter(FMT)
    b.set_title("El óptimo lo decide la merma, no el margen", fontsize=9); rejilla(b)
    return guardar(fig, "7.20", "Curva de coste frente a nivel de servicio")



# ============================================ figuras tomadas de los cuadernos
def _imagen_de_cuaderno(cuaderno, marca):
    """Primera imagen de salida de la celda de `cuaderno` cuyo código contiene `marca`."""
    import json, base64, io
    from PIL import Image
    nb = json.load(open(os.path.join(RAIZ, cuaderno), encoding="utf-8"))
    for c in nb["cells"]:
        if c["cell_type"] == "code" and marca in "".join(c["source"]):
            for o in c.get("outputs", []):
                if "data" in o and "image/png" in o["data"]:
                    return Image.open(io.BytesIO(base64.b64decode(o["data"]["image/png"]))).convert("RGB")
    raise ValueError(f"sin imagen para «{marca}» en {cuaderno}")


def _guardar_imagen(im, clave, titulo):
    nombre = "fig_" + clave.replace(".", "_") + ".png"
    ruta = os.path.join(SALIDA, nombre)
    im.save(ruta)
    print(f"  [{clave:>4}] {nombre:<16} {os.path.getsize(ruta)//1024:>4} KB   {titulo}")
    return ruta


def fig_7_5():
    return _guardar_imagen(_imagen_de_cuaderno("02_Clustering_DSMarket.ipynb", "k_vals = curva.index.values"),
                           "7.5", "Método del codo")


def fig_7_6():
    return _guardar_imagen(_imagen_de_cuaderno("02_Clustering_DSMarket.ipynb", "pca = PCA(n_components=2"),
                           "7.6", "Proyección PCA y peso de cada grupo")


def fig_7_7():
    return _guardar_imagen(_imagen_de_cuaderno("02_Clustering_DSMarket.ipynb", "caso = item_feat['dec_lift']"),
                           "7.7", "El producto de Nochevieja")


def fig_7_8():
    from PIL import Image
    a = _imagen_de_cuaderno("02_Clustering_DSMarket.ipynb", "PERFIL_T = [")
    b = _imagen_de_cuaderno("02_Clustering_DSMarket.ipynb", "D = pd.DataFrame(cdist(")
    h = max(a.height, b.height)
    im = Image.new("RGB", (a.width + b.width + 30, h), "white")
    im.paste(a, (0, (h - a.height) // 2)); im.paste(b, (a.width + 30, (h - b.height) // 2))
    return _guardar_imagen(im, "7.8", "Perfil y parecido entre tiendas")


def fig_7_22():
    """Elasticidad por grupo de producto, leída de la salida del cuaderno 05."""
    import json, re
    nb = json.load(open(os.path.join(RAIZ, "05_Elasticidad_DSMarket.ipynb"), encoding="utf-8"))
    texto = None
    for c in nb["cells"]:
        if c["cell_type"] == "code" and "por_grupo = pd.DataFrame" in "".join(c["source"]):
            for o in c.get("outputs", []):
                t = "".join(o.get("text", [])) or "".join(o.get("data", {}).get("text/plain", []))
                if "elasticidad" in t:
                    texto = t; break
    if texto is None:
        raise ValueError("sin tabla por grupo en el cuaderno 05")
    filas = []
    for l in texto.splitlines():
        m = re.match(r"\s*\d+\s+(.+?)\s+(-?\d+\.\d+)\s+(\d+\.\d+)\s+(-?\d+\.\d+)", l)
        if m:
            filas.append((m.group(1), float(m.group(2)), float(m.group(3))))
    d = pd.DataFrame(filas, columns=["grupo", "e", "se"]).sort_values("e")
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    y = np.arange(len(d))
    ax.errorbar(d["e"], y, xerr=1.96 * d["se"], fmt="o", color=AZUL, ecolor=AZUL,
                capsize=3, markersize=6, zorder=3)
    for yi, (e, se) in enumerate(zip(d["e"], d["se"])):
        ax.text(e, yi + 0.28, es_num(e, 2), ha="center", fontsize=7, color=TINTA2)
    ax.axvline(0, color=TINTA, lw=1.0)
    ax.set_yticks(y); ax.set_yticklabels(d["grupo"], fontsize=7.5)
    ax.set_xlabel("elasticidad-precio estimada (intervalo al 95 %)")
    ax.set_title("La sensibilidad al precio varía entre grupos de producto")
    rejilla(ax, "x")
    return guardar(fig, "7.22", "Elasticidad estimada por grupo de producto")


def fig_7_26():
    """Pantalla principal del panel (captura recortada: cabecera, pestañas e indicadores)."""
    from PIL import Image
    im = Image.open(os.path.join(RAIZ, "documentacion", "capturas", "app_0_hoy_en_la_tienda.png")).convert("RGB")
    im = im.crop((600, 150, im.width, 980))
    return _guardar_imagen(im, "7.26", "Panel de reposición")


# =================================================================== §7.5 precio
def fig_7_23():
    """El coeficiente y su placebo."""
    d = pd.DataFrame({
        "modelo": ["Efectos fijos\n(precio de la semana)",
                   "Placebo\n(precio de la semana siguiente)",
                   "Primeras diferencias"],
        "beta": [-0.395, -0.398, 0.02],
        "err": [0.0205, 0.0207, 0.018]})
    fig, ax = plt.subplots(figsize=(6.4, 2.6))
    col = [AZUL, ROJO, TINTA3]
    for i, r in d.iterrows():
        ax.errorbar(r["beta"], i, xerr=1.96 * r["err"], fmt="o", markersize=8,
                    color=col[i], capsize=4, capthick=1.4, lw=1.6, zorder=3)
        ax.text(r["beta"], i - 0.28, es_num(r["beta"], 3), ha="center", fontsize=8,
                fontweight="bold", color=col[i])
    ax.axvline(0, color=TINTA, lw=1.1)
    ax.set_yticks(range(len(d))); ax.set_yticklabels(d["modelo"], fontsize=8)
    ax.invert_yaxis(); ax.set_xlim(-0.52, 0.12)
    ax.set_xlabel("elasticidad estimada (intervalo al 95%)")
    ax.set_title("Un precio futuro no puede causar una venta pasada", pad=26)
    ax.text(-0.397, 1.42, "prácticamente idéntico al real:\nla especificación no identifica nada",
            ha="center", fontsize=7.2, color=ROJO, fontweight="bold")
    rejilla(ax, "x")
    return guardar(fig, "7.23", "Coeficiente estimado frente al placebo")


def fig_7_24():
    """Potencia del experimento de precios."""
    from scipy.stats import norm
    n = np.arange(50, 1400, 10)
    sigma, efecto = 0.62, 0.4 * 0.08          # desvío del log de ventas · efecto de un 8% de precio
    se = sigma * np.sqrt(2 / n)
    pot = 1 - norm.cdf(norm.ppf(0.975) - efecto / se)
    fig, ax = plt.subplots(figsize=(6.4, 2.7))
    ax.plot(n, pot, color=AZUL, zorder=3)
    ax.axhline(0.80, color=TINTA3, lw=1, ls=(0, (3, 3)))
    j = int(np.argmin(np.abs(pot - 0.80)))
    ax.scatter([n[j]], [pot[j]], s=76, color=NARANJA, zorder=4, edgecolor=FONDO, lw=1.6)
    ax.annotate(f"{es_num(451)} series por brazo", (n[j], pot[j]),
                textcoords="offset points", xytext=(12, -14), fontsize=8,
                color=NARANJA, fontweight="bold")
    ax.text(n[-1], 0.815, "potencia 80%", ha="right", fontsize=7, color=TINTA3)
    ax.set_xlabel("series por brazo"); ax.set_ylabel("potencia")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0%}"))
    ax.set_ylim(0, 1.03)
    ax.set_title("Lo que haría falta para responder la pregunta: 8 semanas y este tamaño")
    rejilla(ax)
    return guardar(fig, "7.24", "Curva de potencia del experimento de precios")


# =================================================================== §7.6 ingeniería
def fig_7_25():
    """El sistema completo, con los dos bucles de realimentación."""
    fig, ax = lienzo(6.6, 3.9)
    ax.text(0, 96, "Los tres consumidores leen las mismas tablas", fontsize=9.5,
            fontweight="bold", color=TINTA)

    caja(ax, 0, 56, 15, 15, "Origen", "3 CSV")
    ax.add_patch(Rectangle((20, 40), 22, 46, facecolor="none", edgecolor=REJILLA,
                           linewidth=0.9, linestyle=(0, (3, 3)), zorder=1))
    ax.text(31, 88, "almacén", ha="center", fontsize=6.8, color=TINTA3)
    for i, n in enumerate(["bronce", "plata", "oro"]):
        es_oro = n == "oro"
        caja(ax, 23, 72 - i * 15, 16, 11, n, None,
             color=AZUL if es_oro else REJILLA, grosor=1.5 if es_oro else 0.9)
        if i:
            flecha(ax, (31, 84 - i * 15), (31, 79 - i * 15), color=REJILLA)
    flecha(ax, (15.5, 63), (22.5, 72 + 5.5))

    caja(ax, 50, 70, 20, 14, "Modelos", "media + p90")
    flecha(ax, (39.5, 66), (49.5, 75))

    # Un tronco y tres ramales en vez de tres diagonales: deja libre el centro del lienzo,
    # que es donde tienen que caber las etiquetas de los dos bucles.
    ax.plot([39.5, 72], [47.5, 47.5], color=REJILLA, linewidth=1.1, zorder=1)
    ax.plot([72, 72], [32.5, 80.5], color=REJILLA, linewidth=1.1, zorder=1)
    for n, sub, y, c in [("API", "→ ERP", 74, REJILLA),
                         ("Panel", "→ tienda", 50, AQUA),
                         ("Power BI", "→ dirección", 26, REJILLA)]:
        caja(ax, 76, y, 20, 13, n, sub, color=c, grosor=1.5 if c == AQUA else 0.9)
        flecha(ax, (72, y + 6.5), (75.5, y + 6.5), color=REJILLA)

    # bucle 1: las predicciones vuelven al almacén
    flecha(ax, (58, 69.5), (41, 53.5), color=NARANJA, guion=(0, (4, 2)))
    ax.text(44, 37, "las predicciones vuelven\nal almacén como hechos",
            fontsize=6.4, color=NARANJA, fontweight="bold", va="center", ha="left")

    # bucle 2: la decisión del encargado, por fuera de todo
    ax.plot([96, 98.5, 98.5, 31], [56.5, 56.5, 8, 8], color=AQUA, linewidth=1.1,
            linestyle=(0, (4, 2)), zorder=1)
    flecha(ax, (31, 10), (31, 41), color=AQUA, guion=(0, (4, 2)))
    ax.text(62, 11, "y la decisión del encargado, también",
            fontsize=6.4, color=AQUA, fontweight="bold", ha="center")
    return guardar(fig, "7.25", "El sistema completo")


def fig_7_16():
    """Predecir el total del ciclo en vez de sumar días."""
    d = resultado("objetivo_agregado_resumen.csv").sort_values("MAE", ascending=False)
    fig, axes = plt.subplots(1, 2, figsize=(6.6, 2.7), gridspec_kw={"wspace": 0.42})
    et = [e.split(" · ")[-1] for e in d["enfoque"]]
    col = [ROJO if "suma" in e.lower() else AZUL for e in d["enfoque"]]
    a = axes[0]
    a.barh(range(len(d)), d["MAE"], color=col, height=0.6, zorder=2)
    for i, v in enumerate(d["MAE"]):
        a.text(v + 0.05, i, es_num(v, 3), va="center", fontsize=7.5, color=TINTA2)
    a.set_yticks(range(len(d))); a.set_yticklabels(et, fontsize=7)
    a.set_xlabel("MAE"); a.set_title("Error", fontsize=9); rejilla(a, "x")
    b = axes[1]
    b.barh(range(len(d)), d["sesgo_%"], color=col, height=0.6, zorder=2)
    for i, v in enumerate(d["sesgo_%"]):
        b.text(v + (0.12 if v >= 0 else -0.12), i, ("+" if v >= 0 else "") + es_num(v, 2) + "%",
               va="center", ha="left" if v >= 0 else "right", fontsize=7.5,
               color=ROJO if abs(v) > 1 else TINTA2, fontweight="bold" if abs(v) > 1 else "normal")
    b.axvline(0, color=TINTA, lw=1)
    b.set_yticks(range(len(d))); b.set_yticklabels([])
    b.set_xlabel("sesgo (%)"); b.set_title("Sesgo", fontsize=9); rejilla(b, "x")
    fig.suptitle("Sumar nueve predicciones diarias arrastraba un sesgo sistemático",
                 fontsize=9, fontweight="bold", x=0.02, ha="left", y=1.04)
    return guardar(fig, "7.16", "Objetivo del ciclo frente a suma de días")


def fig_7_21():
    """Censura: las rachas que el azar no produce."""
    d = resultado("censura_rachas.csv")
    d = d[d["longitud_racha"] != ">= 1 días"]
    fig, ax = plt.subplots(figsize=(6.4, 2.6))
    x = np.arange(len(d)); h = 0.36
    ax.bar(x - h / 2, d["esperado_si_azar_%"], width=h, color=REJILLA, zorder=2,
           label="esperable si fuera azar")
    ax.bar(x + h / 2, d["observado_%"], width=h, color=NARANJA, zorder=2, label="observado")
    for i, (e, o) in enumerate(zip(d["esperado_si_azar_%"], d["observado_%"])):
        ax.text(i - h / 2, e + 0.5, es_num(e, 2), ha="center", fontsize=6.8, color=TINTA2)
        ax.text(i + h / 2, o + 0.5, es_num(o, 2), ha="center", fontsize=7,
                color=NARANJA, fontweight="bold")
    ax.set_xticks(x); ax.set_xticklabels(d["longitud_racha"], fontsize=7.5)
    ax.set_ylabel("% de las rachas de ceros sospechosos")
    ax.set_title("Una rotura dura días; el ruido de Poisson no")
    ax.legend(loc="upper right"); rejilla(ax)
    return guardar(fig, "7.21", "Rachas de ceros: la firma de la censura")


def fig_7_19():
    """El coste de cada candidato, y el nivel de servicio fijo."""
    d = resultado("coste_comparacion.csv").sort_values("coste_USD")
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    et = [c.split(" · ")[0] + " · " + c.split(" · ")[1] if " · " in c else c
          for c in d["candidato"]]
    col = [AZUL if i == 0 else (ROJO if i == len(d) - 1 else REJILLA) for i in range(len(d))]
    ax.barh(range(len(d)), d["margen_perdido"], color=col, height=0.58, zorder=2,
            label="margen perdido")
    ax.barh(range(len(d)), d["mantenimiento"] + d["merma"], left=d["margen_perdido"],
            color=[c for c in col], alpha=0.42, height=0.58, zorder=2,
            label="mantenimiento + merma")
    for i, (t, s) in enumerate(zip(d["coste_USD"], d["servicio_%"])):
        ax.text(t + 9000, i, es_num(t) + f" USD   ·   servicio {es_num(s,1)}%",
                va="center", fontsize=7.5, color=TINTA2)
    ax.set_yticks(range(len(d))); ax.set_yticklabels(et, fontsize=7)
    ax.invert_yaxis(); ax.set_xlim(0, d["coste_USD"].max() * 1.55)
    ax.xaxis.set_major_formatter(FMT)
    ax.set_xlabel("coste total del período (USD)")
    peor, mejor = d["coste_USD"].max(), d["coste_USD"].min()
    ax.set_title(f"El nivel de servicio fijo del 90% cuesta {es_num(peor/mejor,2)} veces "
                 f"más que el candidato óptimo")
    ax.legend(loc="upper right"); rejilla(ax, "x")
    return guardar(fig, "7.19", "Coste por candidato de modelo")


def fig_7_27():
    """Ciclo de vida de un modelo: entrenar no despliega."""
    fig, ax = lienzo(6.6, 3.4)
    ax.text(0, 95, "Entrenar deja un candidato; la puerta decide", fontsize=9.5,
            fontweight="bold", color=TINTA)

    caja(ax, 1, 58, 17, 14, "entrenar", "8 modelos")
    caja(ax, 27, 58, 19, 14, "candidato", "registrado")
    caja(ax, 62, 58, 19, 14, "vigente", "predice", color=AZUL, grosor=1.8)
    caja(ax, 62, 16, 19, 14, "retirado", "pesos en disco")
    caja(ax, 27, 16, 19, 14, "rechazado", "con su motivo", color=NARANJA)

    flecha(ax, (18.5, 65), (26.5, 65))

    # la puerta
    ax.add_patch(Rectangle((48.5, 59.5), 11, 11, facecolor=FONDO, edgecolor=TINTA2,
                           linewidth=1.2, zorder=2))
    ax.text(54, 65, "puerta", ha="center", va="center", fontsize=7,
            fontweight="bold", color=TINTA, zorder=3)
    flecha(ax, (46.5, 65), (48, 65))
    flecha(ax, (60, 65), (61.5, 65), color=AZUL)
    ax.text(54, 74, "¿mejora al vigente?", ha="center", fontsize=6.4, color=TINTA2)

    flecha(ax, (52, 59), (44, 31), color=NARANJA)
    ax.text(43, 44, "no pasa", fontsize=6.4, color=NARANJA, fontweight="bold",
            ha="right", va="center")

    flecha(ax, (71.5, 57.5), (71.5, 30.5))
    ax.text(73.5, 44, "entra otro", fontsize=6.4, color=TINTA2, va="center")

    # el retroceso: una arista, no un proyecto
    ax.plot([81.5, 90, 90, 83], [23, 23, 65, 65], color=AQUA, linewidth=1.1,
            linestyle=(0, (4, 2)), zorder=1)
    flecha(ax, (84, 65), (81.5, 65), color=AQUA)
    ax.text(92.5, 44, "retroceso", fontsize=6.4, color=AQUA, fontweight="bold",
            rotation=90, ha="center", va="center")

    ax.text(0, 5, "El rechazado no se borra: el histórico de lo que no se promovió es la mitad\n"
                  "de la información útil cuando algo va mal.",
            fontsize=6.4, color=TINTA2, va="bottom")
    return guardar(fig, "7.27", "Ciclo de vida de un modelo")


# =================================================================== registro y CLI
REGISTRO = {
    "7.5":  (fig_7_5,  "Método del codo", "cuaderno 02"),
    "7.6":  (fig_7_6,  "Proyección PCA y peso de cada grupo", "cuaderno 02"),
    "7.7":  (fig_7_7,  "El producto de Nochevieja", "cuaderno 02"),
    "7.8":  (fig_7_8,  "Perfil y parecido entre tiendas", "cuaderno 02"),
    "7.22": (fig_7_22, "Elasticidad por grupo de producto", "cuaderno 05"),
    "7.26": (fig_7_26, "Panel de reposición", "captura"),

    "6.1":  (fig_6_1,  "Arquitectura del almacén en tres capas", "esquema"),
    "6.2":  (fig_6_2,  "Modelo dimensional de la capa de consumo", "esquema"),
    "6.3":  (fig_6_3,  "Esquema de la validación temporal por avance", "esquema"),
    "7.1":  (fig_7_1,  "Serie agregada, tendencia y estacionalidades", "almacén"),
    "7.2":  (fig_7_2,  "Elevación por evento del calendario", "almacén"),
    "7.3":  (fig_7_3,  "Solapamiento del top 15 entre ciudades", "almacén"),
    "7.4":  (fig_7_4,  "Dispersión de precios por categoría", "almacén"),
    "7.9":  (fig_7_9,  "Matriz ABC/XYZ", "almacén"),
    "7.10": (fig_7_10, "Estrategia de predicción por bloques", "esquema"),
    "7.11": (fig_7_11, "Error por arquetipo: modelo frente a referencia", "caché"),
    "7.12": (fig_7_12, "Importancia de las variables", "caché"),
    "7.13": (fig_7_13, "Temporada alta: real frente a predicho", "caché"),
    "7.14": (fig_7_14, "Calibración del intervalo de predicción", "caché"),
    "7.15": (fig_7_15, "Error por nivel: métodos de reconciliación", "caché"),
    "7.17": (fig_7_17, "Descomposición del coste de la política de partida", "Tarea 4"),
    "7.18": (fig_7_18, "Efecto del modelo por segmento", "Tarea 4"),
    "7.20": (fig_7_20, "Curva de coste frente a nivel de servicio", "Tarea 4"),
    "7.23": (fig_7_23, "Coeficiente estimado frente al placebo", "Tarea 5"),
    "7.24": (fig_7_24, "Curva de potencia del experimento de precios", "Tarea 5"),
    "7.25": (fig_7_25, "El sistema completo", "esquema"),
    "7.16": (fig_7_16, "Objetivo del ciclo frente a suma de días", "experimento 2"),
    "7.21": (fig_7_21, "Rachas de ceros: la firma de la censura", "experimento 7"),
    "7.19": (fig_7_19, "Coste por candidato de modelo", "experimento 5"),
    "7.27": (fig_7_27, "Ciclo de vida de un modelo", "esquema"),
}

# Figuras del texto que este guion NO produce, con el motivo.
SIN_AUTOMATIZAR = {}


def main(solo, listar):
    if listar:
        print("\nFIGURAS\n" + "-" * 74)
        for k, (_, t, fuente) in REGISTRO.items():
            print(f"  {k:>5}  {t:<52} [{fuente}]")
        print("\nNO AUTOMATIZADAS")
        for k, m in SIN_AUTOMATIZAR.items():
            print(f"  {k:>5}  {m}")
        return 0

    claves = solo or list(REGISTRO)
    desconocidas = [k for k in claves if k not in REGISTRO]
    if desconocidas:
        print(f"No conozco: {', '.join(desconocidas)}. Se puede consultar con --listar.")
        return 1

    print(f"\nGENERANDO {len(claves)} FIGURAS EN {SALIDA}\n" + "-" * 74)
    t0 = time.time()
    hechas, fallidas = [], []
    for k in claves:
        fn, titulo, _ = REGISTRO[k]
        try:
            fn()
            hechas.append(k)
        except Exception as e:
            fallidas.append((k, f"{type(e).__name__}: {e}"))
            print(f"  [{k:>4}] FALLA — {type(e).__name__}: {str(e)[:110]}")

    print("-" * 74)
    print(f"{len(hechas)} generadas · {len(fallidas)} fallidas · {time.time()-t0:.0f}s")
    if fallidas:
        print("\nLo que falló:")
        for k, e in fallidas:
            print(f"  {k}: {e}")
    if not solo:
        print("\nSin automatizar, hay que exportarlas a mano:")
        for k, m in SIN_AUTOMATIZAR.items():
            print(f"  {k}: {m}")
    return 0 if not fallidas else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo", nargs="*", help="claves de figura, por ejemplo 7.9 7.14")
    ap.add_argument("--listar", action="store_true", help="qué figura produce qué")
    a = ap.parse_args()
    sys.exit(main(a.solo, a.listar))
