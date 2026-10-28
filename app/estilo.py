# -*- coding: utf-8 -*-
"""
Estilo de la app: el mismo lenguaje visual que el dashboard de Power BI.

    cabecera azul marino con el logotipo y una línea verde debajo
    fondo gris claro #F3F5F8, tarjetas blancas con borde #9DB7DE
    barra lateral azul marino, pestañas con acento verde
    gráficos con la paleta del tema (dashboard/DSMarket_tema.json)
"""
import base64, os
import altair as alt
import streamlit as st

NAVY, AZUL, VERDE, DORADO = "#0A2A5C", "#2A78D6", "#6A9F1F", "#EDA100"
BORDE, FONDO, SUBTITULO = "#9DB7DE", "#F3F5F8", "#C9D6EA"
COLORES = [NAVY, AZUL, VERDE, DORADO, "#9DB7DE", "#E8743B", "#CD443F", "#8B8B8B", "#DEE5EF"]
RAMPA_AZULES = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#2a78d6", "#1c5cab", "#0d366b"]
FUENTE = "'Segoe UI', 'Helvetica Neue', Arial, sans-serif"

_LOGO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "dsmarket_logo.png")


def _logo_b64() -> str:
    try:
        with open(_LOGO, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except OSError:
        return ""


def _tema_altair():
    return {"config": {
        "background": "transparent", "font": "Segoe UI",
        "view": {"stroke": "transparent"},
        "range": {"category": COLORES, "ramp": RAMPA_AZULES},
        "axis": {"labelColor": "#52514e", "titleColor": NAVY, "gridColor": "#E1E0D9",
                 "domainColor": "#C3C2B7", "tickColor": "#C3C2B7"},
        "legend": {"labelColor": "#52514e", "titleColor": NAVY},
        "title": {"color": NAVY, "fontWeight": "bold", "anchor": "start"}}}


def aplicar(titulo: str, subtitulo: str) -> None:
    """Inyecta el CSS, dibuja la cabecera y activa el tema de los gráficos."""
    alt.themes.register("dsmarket", _tema_altair)
    alt.themes.enable("dsmarket")
    logo = _logo_b64()
    imagen = f"<img src='data:image/png;base64,{logo}' alt='DSMarket'/>" if logo else ""
    st.markdown(f"""<style>
 html, body, [class*="css"], .stApp {{ font-family: {FUENTE}; }}
 .stApp {{ background: {FONDO}; }}
 header[data-testid="stHeader"] {{ display: none; }}
 .block-container {{ padding: 0 2rem 2rem 2rem; max-width: 100%; }}

 /* cabecera: banda azul marino, logotipo en baldosa blanca y línea verde */
 .dsm-cabecera {{ background:{NAVY}; margin:0 -2rem 1.4rem -2rem; padding:12px 24px;
                  border-bottom:4px solid {VERDE}; display:flex; align-items:center; gap:18px; }}
 .dsm-cabecera .logo {{ background:#fff; width:72px; height:72px; border-radius:4px; flex:none;
                        display:flex; align-items:center; justify-content:center; }}
 .dsm-cabecera .logo img {{ width:60px; height:60px; object-fit:contain; }}
 .dsm-cabecera .t {{ color:#fff; font-size:1.7rem; font-weight:700; line-height:1.15; }}
 .dsm-cabecera .s {{ color:{SUBTITULO}; font-size:1rem; margin-top:2px; }}

 h1, h2, h3, h4 {{ color:{NAVY}; font-family:{FUENTE}; }}
 h2 {{ font-size:1.45rem; }}

 /* barra lateral azul marino */
 [data-testid="stSidebar"] {{ background:{NAVY}; }}
 [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3,
 [data-testid="stSidebar"] label, [data-testid="stSidebar"] label p,
 [data-testid="stSidebar"] [data-testid="stCaptionContainer"],
 [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p,
 [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {{ color:#fff; }}
 [data-testid="stSidebar"] [data-testid="stSliderTickBarMin"],
 [data-testid="stSidebar"] [data-testid="stSliderTickBarMax"],
 [data-testid="stSidebar"] [data-testid="stSliderThumbValue"] {{ color:{SUBTITULO}; }}
 [data-testid="stSidebar"] hr {{ border-color:#27497f; }}

 /* tarjetas */
 [data-testid="stMetric"] {{ background:#fff; border:1px solid {BORDE}; border-radius:6px; padding:12px 16px; }}
 [data-testid="stMetricLabel"] p {{ color:#52514e; }}
 [data-testid="stMetricValue"] {{ color:{NAVY}; font-weight:700; }}
 .tarjeta {{ background:#fff; border:1px solid {BORDE}; border-left:4px solid {VERDE};
             padding:0.9rem 1.1rem; border-radius:6px; margin:0.4rem 0; }}
 [data-testid="stAlert"] {{ border:1px solid {BORDE}; background:#fff; }}
 [data-testid="stDataFrame"], [data-testid="stDataEditor"] {{ border:1px solid {BORDE}; border-radius:6px; }}

 /* pestañas: acento verde, como la línea de la cabecera */
 .stTabs [data-baseweb="tab-list"] {{ gap:4px; border-bottom:1px solid {BORDE}; }}
 .stTabs [data-baseweb="tab"] {{ color:{NAVY}; font-weight:600; padding:8px 16px; }}
 .stTabs [aria-selected="true"] {{ color:{NAVY}; }}
 .stTabs [data-baseweb="tab-highlight"] {{ background:{VERDE}; height:3px; }}

 /* botones */
 .stButton > button[kind="primary"] {{ background:{AZUL}; border-color:{AZUL}; color:#fff; font-weight:600; }}
 .stButton > button[kind="primary"]:hover {{ background:{NAVY}; border-color:{NAVY}; }}
</style>
<div class="dsm-cabecera">
  <div class="logo">{imagen}</div>
  <div><div class="t">{titulo}</div><div class="s">{subtitulo}</div></div>
</div>""", unsafe_allow_html=True)
