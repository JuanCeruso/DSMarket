# -*- coding: utf-8 -*-
"""
DSMarket — panel de reposición.

Interfaz sobre el lakehouse y los modelos. Arranque:
    streamlit run app/inicio.py
"""
import os, sys, json
import numpy as np, pandas as pd
import altair as alt
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import datos as D
import estilo
from explicador import explicar, hay_llm

st.set_page_config(page_title="DSMarket · Reposición", page_icon="🛒", layout="wide")
P = D.PALETA

estilo.aplicar("DSMarket · Reposición", "Del pronóstico al estante: pedido sugerido por tienda y producto")

@st.cache_data(show_spinner="Cargando el almacén…")
def cargar():
    return D.cargar()

@st.cache_data(show_spinner=False)
def hist(tienda, item, dias):
    return D.historico(tienda, item, dias)

d = cargar()
series_idx = d["series"].set_index(["item", "store_code"])
prod_idx = d["productos"].set_index("item")

# ------------------------------------------------------------------ barra lateral
with st.sidebar:
    st.subheader("Selección")
    tiendas = d["tiendas"].sort_values("tienda")
    etiqueta = tiendas.apply(lambda r: f"{r['tienda']} · {r['ciudad']}", axis=1).tolist()
    i_tienda = st.selectbox("Tienda", range(len(tiendas)), format_func=lambda i: etiqueta[i])
    tienda = tiendas.iloc[i_tienda]["store_code"]
    parecida = tiendas.set_index("store_code")["tienda"].get(tiendas.iloc[i_tienda]["tienda_mas_parecida"], "—")
    st.caption(f"Tienda más parecida: **{parecida}**")

    st.divider()
    arquetipos = ["(todos)"] + sorted(d["productos"]["arquetipo"].dropna().unique().tolist())
    filtro_arq = st.selectbox("Filtrar por grupo de producto", arquetipos)
    disponibles = series_idx.xs(tienda, level="store_code")
    if filtro_arq != "(todos)":
        items_arq = set(prod_idx.index[prod_idx["arquetipo"] == filtro_arq])
        disponibles = disponibles[disponibles.index.isin(items_arq)]
    disponibles = disponibles.sort_values("facturacion_90d", ascending=False)
    item = st.selectbox(f"Producto ({len(disponibles):,} disponibles, por facturación)",
                        disponibles.index.tolist()[:400])

    st.divider()
    st.subheader("Parámetros de la política")
    dias_rev = st.slider("Días entre revisiones", 1, 21, 7)
    lead = st.slider("Plazo de entrega (días)", 0, 7, 2)
    usar_defecto = st.checkbox("Usar el nivel de servicio del segmento", value=True)
    nivel = None if usar_defecto else st.slider("Nivel de servicio", 0.50, 0.99, 0.90, 0.01)

serie = series_idx.loc[(item, tienda)]
arquetipo = prod_idx.loc[item, "arquetipo"] if item in prod_idx.index else "—"
pred = (d["predicciones"].query("store_code == @tienda and item == @item")
        .sort_values("fecha").reset_index(drop=True))

tab0, tab1, tab2, tab3, tab5, tab4 = st.tabs(["Hoy en la tienda", "Reposición",
                                              "Explorador del catálogo", "Curva de servicio",
                                              "Preguntar", "Cómo se integra"])

# ------------------------------------------------------------------ 1. reposición
with tab1:
    st.header(f"{item}")
    c = st.columns([1, 1, 1, 1])
    c[0].metric("Segmento", serie["celda"])
    c[1].metric("Grupo de producto", arquetipo)
    c[2].metric("Coef. de variación", f"{serie['coef_variacion']:.2f}")
    c[3].metric("Facturación 90 días", f"${serie['facturacion_90d']:,.0f}")

    izq, der = st.columns([2, 1])
    with der:
        st.subheader("Situación en tienda")
        stock = st.number_input("Stock actual (unidades)", 0.0, 1e5,
                                float(round(serie["media_dia"] * 5, 0)), 1.0)
        transito = st.number_input("Ya pedido, en camino", 0.0, 1e5, 0.0, 1.0)
        r = D.sugerir(pred, serie, stock, transito, dias_rev, lead, nivel)
        st.divider()
        st.metric("PEDIDO SUGERIDO", f"{r['pedido']:,} uds",
                  delta=f"cubre {r['cobertura']} días", delta_color="off")
        m = st.columns(2)
        m[0].metric("Demanda esperada", f"{r['demanda_esperada']:.0f}")
        m[1].metric("Stock de seguridad", f"{r['stock_seguridad']:.0f}")
        st.caption(f"Nivel objetivo {r['nivel_objetivo']:.0f} uds · servicio {r['servicio']:.0%} · {r['metodo']}")

    with izq:
        st.subheader("Demanda: histórico y previsión")
        h = hist(tienda, item, 90).rename(columns={"unidades": "valor"})
        h["tipo"] = "Real"
        f = pred.head(28).rename(columns={"prediccion_media": "valor"})[["fecha", "valor", "prediccion_p90"]]
        f["tipo"] = "Previsión"
        banda = alt.Chart(f).mark_area(opacity=0.18, color=P["dorado"]).encode(
            x=alt.X("fecha:T", title=None), y=alt.Y("valor:Q", title="unidades / día"),
            y2="prediccion_p90:Q")
        lineas = alt.Chart(pd.concat([h[["fecha", "valor", "tipo"]], f[["fecha", "valor", "tipo"]]])).mark_line(
            point=False).encode(
            x="fecha:T", y="valor:Q",
            color=alt.Color("tipo:N", scale=alt.Scale(domain=["Real", "Previsión"],
                                                      range=[P["gris"], P["azul"]]), title=None),
            tooltip=["fecha:T", alt.Tooltip("valor:Q", format=".2f"), "tipo:N"])
        st.altair_chart((banda + lineas).properties(height=300), width='stretch')
        st.caption("La banda dorada llega hasta el percentil 90: es el nivel que la demanda no supera "
                   "9 de cada 10 días, y es lo que dimensiona el stock de seguridad.")

    st.subheader("Por qué este número")
    base = D.explicacion_base(serie, r, arquetipo)
    if hay_llm():
        if st.button("Explicar en lenguaje natural"):
            with st.spinner("Redactando…"):
                st.markdown(f"<div class='tarjeta'>{explicar(item, tienda, serie, r, arquetipo)}</div>",
                            unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='tarjeta'>{base}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='tarjeta'>{base}</div>", unsafe_allow_html=True)
        st.caption("💡 Con una clave de API configurada (ANTHROPIC_API_KEY), esta explicación se "
                   "redacta en lenguaje natural para el encargado de tienda.")

# ------------------------------------------------------------------ 2. explorador
with tab2:
    st.header("El catálogo, segmentado")
    s = d["series"].copy()
    matriz = s.pivot_table(index="clase_abc", columns="clase_xyz", values="item", aggfunc="count")
    fact = (s.groupby(["clase_abc", "clase_xyz"])["facturacion_90d"].sum()
            / s["facturacion_90d"].sum() * 100).unstack()
    c1, c2 = st.columns(2)
    for col, tabla, titulo, fmt in [(c1, matriz, "Series producto-tienda", ",.0f"),
                                    (c2, fact, "% de la facturación", ".1f")]:
        largo = tabla.reset_index().melt("clase_abc", var_name="clase_xyz", value_name="v")
        grafico = alt.Chart(largo).mark_rect().encode(
            x=alt.X("clase_xyz:N", title="XYZ (predictibilidad)"),
            y=alt.Y("clase_abc:N", title="ABC (valor)"),
            color=alt.Color("v:Q", scale=alt.Scale(range=estilo.RAMPA_AZULES), legend=None))
        texto = grafico.mark_text(fontSize=13).encode(
            text=alt.Text("v:Q", format=fmt),
            color=alt.condition(alt.datum.v > largo["v"].max() * 0.5, alt.value("white"), alt.value(P["navy"])))
        col.subheader(titulo)
        col.altair_chart((grafico + texto).properties(height=220), width='stretch')
    st.info("**AX** concentra el 56% de la facturación con demanda estable: es donde automatizar rinde más. "
            "**CZ** es el 28% del catálogo por el 3,5% de la facturación: ahí el modelo gana al histórico, y conviene revisar el surtido.")

    st.subheader(f"Mayores pedidos sugeridos en {tiendas.iloc[i_tienda]['tienda']}")
    top = disponibles.head(15).copy()
    filas = []
    for it, sr in top.iterrows():
        ps = d["predicciones"].query("store_code == @tienda and item == @it").sort_values("fecha")
        if ps.empty: continue
        rr = D.sugerir(ps, sr, sr["media_dia"] * 3, 0, dias_rev, lead, nivel)
        filas.append({"producto": it, "segmento": sr["celda"],
                      "grupo": prod_idx.loc[it, "arquetipo"] if it in prod_idx.index else "—",
                      "demanda 9d": round(rr["demanda_esperada"], 1),
                      "nivel objetivo": round(rr["nivel_objetivo"], 1),
                      "pedido": rr["pedido"], "servicio": f"{rr['servicio']:.0%}"})
    st.dataframe(pd.DataFrame(filas), width='stretch', hide_index=True)

# ------------------------------------------------------------------ 3. curva
with tab3:
    st.header("Cuánto cuesta cada punto de servicio")
    st.markdown("Resultado de la simulación de la Tarea 4 sobre las 30.490 series durante 4 semanas "
                "con la demanda real observada.")
    curva = pd.DataFrame({
        "nivel_objetivo": [0.50, 0.70, 0.80, 0.85, 0.90, 0.95, 0.98, 0.99],
        "servicio_real": [86.3, 91.4, 93.5, 94.5, 95.5, 96.6, 97.5, 97.9],
        "margen_perdido": [161353, 97978, 72848, 61075, 49269, 36588, 26861, 22231],
        "mantenimiento": [11527, 15010, 17228, 18622, 20401, 23083, 26144, 28202]})
    curva["coste_total"] = curva["margen_perdido"] + curva["mantenimiento"]
    merma = st.select_slider("Merma sobre el remanente (lo que se descarta y no se vende)",
                             options=[0, 2, 5, 10, 20], value=0, format_func=lambda v: f"{v}%")
    remanente = np.array([147183, 200677, 235338, 257189, 285227, 327592, 376097, 408796])
    curva["merma"] = remanente * 3.14 * (merma / 100)
    curva["total_con_merma"] = curva["coste_total"] + curva["merma"]
    optimo = curva.loc[curva["total_con_merma"].idxmin(), "nivel_objetivo"]
    st.metric("Nivel de servicio óptimo con esa merma", f"{optimo:.0%}")
    largo = curva.melt("nivel_objetivo", value_vars=["margen_perdido", "mantenimiento", "merma"],
                       var_name="componente", value_name="usd")
    barras = alt.Chart(largo).mark_bar().encode(
        x=alt.X("nivel_objetivo:O", title="nivel de servicio objetivo",
                axis=alt.Axis(format=".0%")),
        y=alt.Y("usd:Q", title="coste 28 días (USD)"),
        color=alt.Color("componente:N", scale=alt.Scale(
            domain=["margen_perdido", "mantenimiento", "merma"],
            range=[P["dorado"], P["azul"], P["verde"]]), title=None))
    st.altair_chart(barras.properties(height=340), width='stretch')
    st.warning("El nivel óptimo lo decide **la merma, no el margen**. Mover el margen bruto entre el 10% "
               "y el 35% deja el óptimo en 98-99%; una merma del 10% lo baja al 90% y del 20%, al 80%. "
               "Es el número que hay que ir a medir.")

# ------------------------------------------------------------------ 4. integración
with tab4:
    st.header("Cómo se integra con los sistemas de DSMarket")
    st.markdown("""
El panel es una vista. La integración real es la **API de reposición**, que responde la misma
pregunta desde el ERP o el sistema de tienda. Esta pestaña muestra la petición equivalente a lo
que estás viendo en la pestaña de Reposición.
""")
    peticion = {"tienda": tienda, "fecha_revision": str(pred["fecha"].min().date()),
                "productos": [{"item": item, "stock_actual": float(stock), "en_transito": float(transito)}],
                "parametros": {"dias_revision": dias_rev, "lead_time": lead,
                               **({} if nivel is None else {"nivel_servicio": nivel})}}
    respuesta = {"tienda": tienda, "cobertura_hasta": str(pred["fecha"].iloc[r["cobertura"] - 1].date()),
                 "sugerencias": [{"item": item, "segmento": serie["celda"],
                                  "demanda_esperada": round(r["demanda_esperada"], 2),
                                  "nivel_objetivo": round(r["nivel_objetivo"], 2),
                                  "pedido_sugerido": r["pedido"],
                                  "nivel_servicio_aplicado": r["servicio"],
                                  "metodo": r["metodo"], "motivo": "…"}]}
    c1, c2 = st.columns(2)
    c1.subheader("POST /reposicion/sugerencia")
    c1.code(json.dumps(peticion, indent=2, ensure_ascii=False), language="json")
    c2.subheader("Respuesta")
    c2.code(json.dumps(respuesta, indent=2, ensure_ascii=False), language="json")
    st.markdown("""
**El flujo completo, de la fuente al estante:**

```
CSV / sistemas fuente
   └─► lakehouse: bronze → silver → gold        (pipeline.py, diario)
          └─► modelos: LightGBM media + p90     (semanal, ~2 min)
                 └─► gold: fact_predicciones + fact_reposicion
                        ├─► API de reposición  → ERP / sistema de compras
                        ├─► este panel         → equipo comercial
                        └─► PowerBI            → dirección
```

Todo lo que se ve aquí sale de `lakehouse/gold/`. No hay ficheros sueltos ni hojas de cálculo
intermedias: el dashboard, la API y este panel leen exactamente los mismos datos.
""")


# ------------------------------------------------------------------ 5. preguntar
with tab5:
    st.header("Preguntar al almacén en lenguaje natural")
    st.markdown("""
Se escribe una pregunta de negocio y el sistema la traduce a SQL, la ejecuta contra el almacén
y muestra el resultado. **El modelo de lenguaje no calcula nada**: genera la consulta, la
aritmética la hace la base de datos, y el SQL se muestra siempre para que se pueda auditar.
""")
    ejemplos = ["¿Qué 10 productos facturaron más en Brooklyn en 2016?",
                "¿Cuántas unidades se vendieron por ciudad y mes en 2015?",
                "¿Qué productos del segmento AX tienen el mayor stock de seguridad sugerido?",
                "¿Qué días con evento tuvieron más ventas totales?"]
    pregunta = st.text_input("Pregunta", placeholder=ejemplos[0])
    st.caption("Ejemplos: " + " · ".join(f"*{e}*" for e in ejemplos))

    if not hay_llm():
        st.info("Esta función necesita una clave de API configurada en la variable de entorno "
                "`ANTHROPIC_API_KEY`. Sin ella, el resto del panel funciona igual: la traducción "
                "a SQL es lo único que requiere el modelo de lenguaje.")
    elif pregunta:
        from explicador import consultar, resumir_resultado
        with st.spinner("Traduciendo a SQL…"):
            sql, error = consultar(pregunta)
        if error:
            st.error(f"No se pudo ejecutar: {error}")
            if sql:
                st.code(sql, language="sql")
        else:
            st.subheader("Consulta generada")
            st.code(sql, language="sql")
            try:
                import duckdb
                con = duckdb.connect()
                for t in ["fact_ventas", "fact_predicciones", "fact_reposicion", "dim_producto",
                          "dim_tienda", "dim_serie", "dim_calendario", "mart_ventas_dia",
                          "mart_producto_tienda"]:
                    con.execute(f"CREATE OR REPLACE VIEW {t} AS "
                                f"SELECT * FROM read_parquet('{os.path.join(D.GOLD, t)}.parquet')")
                tabla = con.execute(sql).df()
                con.close()
                st.subheader(f"Resultado · {len(tabla)} filas")
                st.dataframe(tabla, width='stretch', hide_index=True)
                resumen = resumir_resultado(pregunta, sql, tabla)
                if resumen:
                    st.markdown(f"<div class='tarjeta'>{resumen}</div>", unsafe_allow_html=True)
            except Exception as e:
                st.error(f"La consulta generada no se pudo ejecutar: {e}")


# ------------------------------------------------------------------ 0. hoy en la tienda
with tab0:
    st.header(f"Hoy en {tiendas.iloc[i_tienda]['tienda']}")
    st.markdown("""
La lista de trabajo del día: qué referencias necesitan pedido, ordenadas por lo que cuesta no
pedirlas. **Revisión por excepción** — se confirma la lista entera y solo se interviene donde
haya desacuerdo.
""")
    c = st.columns([1, 1, 2])
    cobertura_actual = c[0].slider("Días de stock estimado", 1.0, 15.0, 5.0, 0.5,
                                   help="Sustituto del inventario real, que el sistema todavía "
                                        "no recibe. En producción viene del sistema de stock.")
    cuantas = c[1].number_input("Referencias a revisar", 10, 200, 25, 5)

    with st.spinner("Calculando la lista…"):
        pend = D.pendientes(tienda, dias_rev, lead, nivel, cobertura_actual)

    if pend.empty:
        st.info("No hay predicciones cargadas para esta tienda.")
    else:
        con_pedido = pend[pend["pedido_sugerido"] > 0].head(int(cuantas)).copy()
        m = st.columns(4)
        m[0].metric("Referencias a pedir", f"{len(pend[pend['pedido_sugerido']>0]):,}")
        m[1].metric("Unidades sugeridas", f"{int(pend['pedido_sugerido'].sum()):,}")
        m[2].metric("En riesgo de rotura",
                    f"{int((pend['excepcion']=='riesgo de rotura').sum()):,}")
        m[3].metric("Con exceso de cobertura",
                    f"{int((pend['excepcion']=='exceso de cobertura').sum()):,}")

        st.subheader("Lista de pedido")
        st.caption("La columna «pedido final» es editable: se cambia lo que no cuadre y se confirma "
                   "abajo. Lo que se guarda es la diferencia entre lo sugerido y lo pedido.")
        editable = con_pedido[["item", "segmento", "excepcion", "dias_de_cobertura",
                               "demanda_ciclo", "nivel_objetivo", "pedido_sugerido"]].copy()
        editable["dias_de_cobertura"] = editable["dias_de_cobertura"].round(1)
        editable["pedido_final"] = editable["pedido_sugerido"]
        editado = st.data_editor(
            editable, hide_index=True, width='stretch',
            disabled=[c for c in editable.columns if c != "pedido_final"],
            column_config={
                "item": "producto",
                "excepcion": "aviso",
                "dias_de_cobertura": st.column_config.NumberColumn("días de stock", format="%.1f"),
                "demanda_ciclo": st.column_config.NumberColumn("demanda 9 d", format="%.1f"),
                "nivel_objetivo": st.column_config.NumberColumn("nivel objetivo", format="%.1f"),
                "pedido_sugerido": "sugerido",
                "pedido_final": st.column_config.NumberColumn(
                    "pedido final", min_value=0, step=1,
                    help="Se cambia el número si no se está de acuerdo con la sugerencia.")})

        cambios = int((editado["pedido_final"] != editado["pedido_sugerido"]).sum())
        c1, c2 = st.columns([1, 3])
        if c1.button("Confirmar el pedido", type="primary"):
            filas = [{"tienda": tienda, "item": r["item"], "segmento": r["segmento"],
                      "pedido_sugerido": int(r["pedido_sugerido"]),
                      "pedido_final": int(r["pedido_final"]),
                      "dias_revision": dias_rev, "lead_time": lead,
                      "fecha_revision": str(pred["fecha"].min().date())}
                     for _, r in editado.iterrows()]
            total = D.registrar_decisiones(filas)
            st.success(f"{len(filas)} líneas registradas · {cambios} modificadas respecto de lo "
                       f"sugerido · {total} decisiones acumuladas en el histórico.")
        c2.caption(f"{cambios} de {len(editado)} líneas modificadas.")

        hist = D.historico_decisiones()
        if not hist.empty:
            st.subheader("Qué dice el histórico de decisiones")
            hist["diferencia"] = hist["pedido_final"] - hist["pedido_sugerido"]
            res = hist.groupby("segmento").agg(
                lineas=("item", "count"),
                aceptadas=("diferencia", lambda x: (x == 0).mean()),
                sesgo_medio=("diferencia", "mean")).round(3)
            res.columns = ["líneas", "% aceptadas sin cambio", "diferencia media"]
            st.dataframe(res, width='stretch')
            st.caption("Un segmento con muchas correcciones en la misma dirección indica que el "
                       "sistema se equivoca de forma sistemática ahí, y es exactamente la señal "
                       "que hoy no se podía medir.")
