# -*- coding: utf-8 -*-
"""
Parche de la aplicación: vista de tienda completa y registro de la decisión.

Aplica dos cambios sobre `app/`:

  1. **«Hoy en la tienda»** — una pestaña nueva, que pasa a ser la primera. El flujo actual
     obliga a elegir un producto de a uno; un encargado real no hace eso. Llega, quiere ver las
     referencias que necesitan pedido hoy ordenadas por urgencia, y revisar solo las excepciones.
  2. **Registro de la decisión** — un formulario que guarda lo que el encargado pidió realmente
     frente a lo sugerido. Es el dato que falta para poder medir si el sistema sirve, y el que
     convierte el proyecto en un sistema que aprende.

Ejecutar desde PROYECTO/:

    python3 parches/aplicar_app.py            # comprueba y aplica
    python3 parches/aplicar_app.py --revisar  # solo comprueba que los anclajes existen

El parche es idempotente: si ya está aplicado, avisa y no hace nada. Antes de tocar nada crea una
copia de seguridad con la extensión .bak.
"""
from __future__ import annotations
import argparse, os, shutil, sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(RAIZ, "app")

# ---------------------------------------------------------------- datos.py
FUNCIONES_DATOS = '''

# ---------------------------------------------------------------- vista de tienda
def pendientes(tienda: str, dias_revision: int, lead_time: int, nivel_servicio,
               cobertura_dias: float = 5.0, limite: int = 400) -> pd.DataFrame:
    """Las series de una tienda ordenadas por urgencia de pedido.

    El stock real no existe en el sistema, asi que se simula como `cobertura_dias` de venta
    media. En explotacion este es el punto exacto donde entra el dato del inventario: se
    sustituye esa linea y el resto de la funcion no cambia.
    """
    d = cargar()
    series = d["series"]
    series = series[series["store_code"] == tienda].copy()
    series = series.sort_values("facturacion_90d", ascending=False).head(limite)
    pred = d["predicciones"]
    pred = pred[pred["store_code"] == tienda]

    filas = []
    for _, s in series.iterrows():
        ps = pred[pred["item"] == s["item"]].sort_values("fecha")
        if ps.empty:
            continue
        stock = float(s["media_dia"]) * cobertura_dias        # <- sustituir por el stock real
        r = sugerir(ps, s, stock, 0.0, dias_revision, lead_time, nivel_servicio)
        deficit = r["nivel_objetivo"] - stock
        filas.append({
            "item": s["item"], "segmento": s["celda"],
            "stock_estimado": round(stock, 1),
            "demanda_ciclo": round(r["demanda_esperada"], 1),
            "nivel_objetivo": round(r["nivel_objetivo"], 1),
            "pedido_sugerido": r["pedido"],
            "servicio": r["servicio"],
            "urgencia": float(max(deficit, 0) * s["facturacion_90d"] / 90.0),
            "dias_de_cobertura": float(stock / max(s["media_dia"], 1e-6)),
        })
    df = pd.DataFrame(filas)
    if df.empty:
        return df
    df["excepcion"] = ""
    df.loc[df["dias_de_cobertura"] < 2, "excepcion"] = "riesgo de rotura"
    df.loc[df["pedido_sugerido"] == 0, "excepcion"] = "no hace falta pedir"
    df.loc[df["dias_de_cobertura"] > 30, "excepcion"] = "exceso de cobertura"
    return df.sort_values("urgencia", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------- registro de decisiones
DECISIONES = os.path.join(GOLD, "fact_decisiones.parquet")


def registrar_decisiones(filas: list) -> int:
    """Guarda lo que el encargado pidio realmente frente a lo sugerido.

    Escritura atomica mediante fichero temporal: si el proceso muere a mitad, el historico
    anterior sigue siendo legible.
    """
    import datetime as _dt
    if not filas:
        return 0
    nuevo = pd.DataFrame(filas)
    nuevo["momento"] = _dt.datetime.now().isoformat(timespec="seconds")
    if os.path.exists(DECISIONES):
        nuevo = pd.concat([pd.read_parquet(DECISIONES), nuevo], ignore_index=True)
    tmp = DECISIONES + ".tmp"
    nuevo.to_parquet(tmp, index=False)
    os.replace(tmp, DECISIONES)
    return len(nuevo)


def historico_decisiones() -> pd.DataFrame:
    return pd.read_parquet(DECISIONES) if os.path.exists(DECISIONES) else pd.DataFrame()
'''

# ---------------------------------------------------------------- inicio.py
TABS_VIEJO = ('tab1, tab2, tab3, tab5, tab4 = st.tabs(["Reposición", "Explorador del catálogo",\n'
              '                                        "Curva de servicio", "Preguntar", "Cómo se integra"])')
TABS_NUEVO = ('tab0, tab1, tab2, tab3, tab5, tab4 = st.tabs(["Hoy en la tienda", "Reposición",\n'
              '                                              "Explorador del catálogo", "Curva de servicio",\n'
              '                                              "Preguntar", "Cómo se integra"])')

PESTANA_HOY = '''

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
        st.caption("La columna «pedido final» es editable: cambiá lo que no te cuadre y confirmá "
                   "abajo. Lo que se guarda es la diferencia entre lo sugerido y lo que pediste.")
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
                    help="Cambiá el número si no estás de acuerdo con la sugerencia.")})

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
'''


def leer(p):
    return open(p, encoding="utf-8").read()


def main(revisar):
    fdatos = os.path.join(APP, "datos.py")
    finicio = os.path.join(APP, "inicio.py")
    for f in (fdatos, finicio):
        if not os.path.exists(f):
            sys.exit(f"No encuentro {f}. Ejecutá este parche desde la carpeta PROYECTO/.")

    datos, inicio = leer(fdatos), leer(finicio)
    if "def pendientes(" in datos or "with tab0:" in inicio:
        print("El parche ya está aplicado. No se toca nada.")
        return

    problemas = []
    if TABS_VIEJO not in inicio:
        problemas.append("No encuentro la línea de st.tabs esperada en app/inicio.py. "
                         "Si la editaste a mano, aplicá el cambio a mano: los dos bloques de "
                         "código están en este mismo fichero, en FUNCIONES_DATOS y PESTANA_HOY.")
    if "def sugerir(" not in datos or "GOLD" not in datos:
        problemas.append("app/datos.py no tiene la forma esperada (falta sugerir o GOLD).")
    if problemas:
        for p in problemas:
            print("  ·", p)
        sys.exit(1)

    print("  anclajes encontrados en app/datos.py y app/inicio.py")
    if revisar:
        print("  (--revisar: no se ha modificado nada)")
        return

    shutil.copy2(fdatos, fdatos + ".bak")
    shutil.copy2(finicio, finicio + ".bak")
    open(fdatos, "w", encoding="utf-8").write(datos + FUNCIONES_DATOS)
    open(finicio, "w", encoding="utf-8").write(
        inicio.replace(TABS_VIEJO, TABS_NUEVO, 1) + PESTANA_HOY)

    import py_compile
    for f in (fdatos, finicio):
        py_compile.compile(f, doraise=True)

    print("""
  aplicado:
    · app/datos.py    + pendientes(), registrar_decisiones(), historico_decisiones()
    · app/inicio.py   + pestaña «Hoy en la tienda», ahora la primera
    · copias de seguridad en .bak

  arrancá con:  streamlit run app/inicio.py

  Las decisiones se guardan en lakehouse/gold/fact_decisiones.parquet, dentro del mismo
  almacén que todo lo demás: el monitor y el cuadro de mando las leen con el mismo SQL.""")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--revisar", action="store_true", help="comprobar sin modificar")
    a = ap.parse_args()
    main(a.revisar)
