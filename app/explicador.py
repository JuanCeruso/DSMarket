# -*- coding: utf-8 -*-
"""
Capa de lenguaje natural.

**Regla de diseño que gobierna todo este módulo: el modelo de lenguaje NUNCA calcula.**
Recibe cifras ya calculadas por la política y las redacta; o traduce una pregunta a SQL que
se ejecuta después contra el almacén y cuyos resultados se muestran tal cual. Un LLM que
inventa una cifra de stock en un contexto financiero es un pasivo, no una funcionalidad.

De ahí las tres barreras:
  1. El prompt del explicador lleva los números resueltos y prohíbe explícitamente calcular.
  2. El consultor genera SQL, no respuestas: la aritmética la hace DuckDB.
  3. El SQL generado se valida (solo SELECT, solo vistas conocidas, con LIMIT) y se muestra
     al usuario antes de ejecutarlo.
"""
from __future__ import annotations
import os, re

# El identificador por defecto se puede cambiar sin tocar el código:
#     export DSMARKET_LLM_MODELO="claude-haiku-4-5-20251001"   (más barato y rápido)
TABLAS_PERMITIDAS = {"fact_ventas", "fact_predicciones", "fact_reposicion", "dim_producto",
                     "dim_tienda", "dim_serie", "dim_calendario", "mart_ventas_dia",
                     "mart_producto_tienda"}

# --------------------------------------------------------------- proveedor
# El proveedor es una variable de entorno, no una decisión de código. Casi todos exponen una
# interfaz compatible con la de OpenAI, así que una sola rama cubre Ollama, Groq, Gemini y
# OpenRouter; Anthropic conserva la suya porque su SDK usa otra forma.
#
#     export DSMARKET_LLM=ollama     -> local, sin clave ni coste
#
PREAJUSTES = {
    "ollama":     ("openai", "http://localhost:11434/v1",
                   "llama3.1:8b",                      None),
    "groq":       ("openai", "https://api.groq.com/openai/v1",
                   "llama-3.3-70b-versatile",          "GROQ_API_KEY"),
    "gemini":     ("openai", "https://generativelanguage.googleapis.com/v1beta/openai/",
                   "gemini-2.5-flash",                 "GEMINI_API_KEY"),
    "openrouter": ("openai", "https://openrouter.ai/api/v1",
                   "meta-llama/llama-3.3-70b-instruct:free", "OPENROUTER_API_KEY"),
    "anthropic":  ("anthropic", None,
                   "claude-sonnet-5",                  "ANTHROPIC_API_KEY"),
}


def _config() -> dict:
    """Resuelve proveedor, URL, modelo y clave a partir del entorno."""
    nombre = os.environ.get("DSMARKET_LLM", "").strip().lower()
    if nombre not in PREAJUSTES:
        nombre = "anthropic"          # comportamiento anterior por defecto
    familia, url, modelo, var_clave = PREAJUSTES[nombre]
    return {
        "proveedor": nombre,
        "familia": familia,
        "base_url": os.environ.get("DSMARKET_LLM_BASE_URL", url),
        "modelo": os.environ.get("DSMARKET_LLM_MODELO", modelo),
        "clave": os.environ.get(var_clave, "") if var_clave else "local-sin-clave",
        "necesita_clave": var_clave is not None,
        "var_clave": var_clave,
    }


CFG = _config()
MODELO = CFG["modelo"]


def hay_llm() -> bool:
    """True si la capa de lenguaje puede usarse. Nunca lanza: si algo falta, devuelve False."""
    if CFG["necesita_clave"] and not CFG["clave"]:
        return False
    try:
        if CFG["familia"] == "anthropic":
            import anthropic  # noqa: F401
        else:
            import openai  # noqa: F401
    except ImportError:
        return False
    if CFG["proveedor"] == "ollama":
        # sin servidor levantado no hay capa de lenguaje, y hay que saberlo antes de pintar el botón
        try:
            import urllib.request
            urllib.request.urlopen(CFG["base_url"].replace("/v1", "/api/tags"), timeout=1.5)
        except Exception:
            return False
    return True


def _cliente():
    if CFG["familia"] == "anthropic":
        import anthropic
        return anthropic.Anthropic()
    import openai
    return openai.OpenAI(base_url=CFG["base_url"], api_key=CFG["clave"] or "sin-clave")


def _preguntar(sistema: str, usuario: str, max_tokens: int = 500) -> str:
    if CFG["familia"] == "anthropic":
        respuesta = _cliente().messages.create(
            model=MODELO, max_tokens=max_tokens, temperature=0.2,
            system=sistema, messages=[{"role": "user", "content": usuario}])
        return respuesta.content[0].text.strip()
    respuesta = _cliente().chat.completions.create(
        model=MODELO, max_tokens=max_tokens, temperature=0.2,
        messages=[{"role": "system", "content": sistema},
                  {"role": "user", "content": usuario}])
    return respuesta.choices[0].message.content.strip()

# --------------------------------------------------------------- explicador
SISTEMA_EXPLICADOR = """Sos analista de reposición en DSMarket, una cadena de supermercados.
Escribes para el encargado de una tienda: alguien práctico, con poco tiempo, que necesita
entender por qué el sistema le sugiere pedir esa cantidad y decidir si le hace caso.

Reglas estrictas:
- NO calcules ni estimes ningún número. Usa exclusivamente las cifras que se facilitan.
- NO inventes causas que no estén en los datos (clima, competencia, promociones).
- Máximo 4 frases, en español rioplatense neutro, sin tecnicismos innecesarios.
- Si la confianza es baja, decilo con claridad: el encargado tiene que saber cuándo dudar.
- No uses viñetas ni títulos. Prosa directa."""

def explicar(item: str, tienda: str, serie, resultado: dict, arquetipo: str) -> str:
    """Redacta la justificación del pedido. Si no hay LLM, cae en la explicación por reglas."""
    if not hay_llm():
        from datos import explicacion_base
        return explicacion_base(serie, resultado, arquetipo)
    contexto = f"""Producto: {item}   Tienda: {tienda}
Segmento ABC/XYZ: {serie['celda']}  (A/B/C = peso en facturación; X/Y/Z = predictibilidad)
Grupo de producto: {arquetipo}
Coeficiente de variación de la demanda diaria: {serie['coef_variacion']:.2f}
Días sin ninguna venta en los últimos 90 días: {serie['frac_dias_sin_venta']:.0%}
Facturación de los últimos 90 días: {serie['facturacion_90d']:,.0f} USD
Venta media diaria: {serie['media_dia']:.2f} unidades

Decisión calculada por el sistema:
- Período a cubrir: {resultado['cobertura']} días
- Demanda esperada en ese período: {resultado['demanda_esperada']:.1f} unidades
- Stock de seguridad: {resultado['stock_seguridad']:.1f} unidades
- Nivel objetivo: {resultado['nivel_objetivo']:.1f} unidades
- Stock disponible ahora (incluye lo que viene en camino): {resultado['posicion']:.0f}
- PEDIDO SUGERIDO: {resultado['pedido']} unidades
- Nivel de servicio objetivo: {resultado['servicio']:.0%}
- Método usado: {resultado['metodo']}

Explicá esta sugerencia."""
    try:
        return _preguntar(SISTEMA_EXPLICADOR, contexto)
    except Exception as e:
        from datos import explicacion_base
        return explicacion_base(serie, resultado, arquetipo) + f"\n\n*(No se pudo usar el modelo: {e})*"

# --------------------------------------------------------------- consultas
SISTEMA_SQL = """Traducís preguntas de negocio a SQL de DuckDB sobre el almacén de DSMarket.

Esquema disponible (todas son vistas ya registradas):
  fact_ventas(fecha DATE, item, store_code, unidades, precio, importe)      -- grano diario, 2011-2016
  fact_predicciones(item, store_code, fecha, prediccion_media, prediccion_p90)
  fact_reposicion(fecha_revision, item, store_code, segmento, demanda_esperada,
                  nivel_objetivo, stock_seguridad, nivel_servicio, metodo)
  dim_producto(item, categoria, departamento, grupo_producto, arquetipo)   -- arquetipo = nombre del grupo de producto
  dim_tienda(store_code, tienda, ciudad, tienda_mas_parecida)
  dim_serie(item, store_code, unidades_90d, facturacion_90d, media_dia, desvio_dia,
            frac_dias_sin_venta, coef_variacion, clase_abc, clase_xyz)
  dim_calendario(fecha, dia_semana, anio, mes, semana_iso, evento, es_fin_de_semana,
                 es_dia_cierre, es_temporada_alta)
  mart_ventas_dia(fecha, ciudad, tienda, categoria, departamento, unidades, importe)

Reglas:
- Devolvé ÚNICAMENTE la consulta SQL, sin explicación, sin ``` y sin punto y coma final.
- Una sola sentencia SELECT. Nunca INSERT, UPDATE, DELETE, CREATE, DROP, COPY ni ATTACH.
- Incluí siempre un LIMIT (máximo 200 filas).
- fact_ventas tiene 58 millones de filas: filtrá por fecha o agregá siempre que puedas, y
  usa mart_ventas_dia cuando la pregunta sea de nivel ciudad/tienda/departamento.
- Cuidado con el fan-out: fact_ventas es diaria y fact_reposicion semanal. Si hay que
  combinarlas, agregá cada una por separado en CTEs y unilas después.
- Nombrá las columnas de salida en español."""

PROHIBIDO = re.compile(r"\b(insert|update|delete|drop|create|alter|copy|attach|pragma|export)\b", re.I)

def validar_sql(sql: str) -> tuple[bool, str]:
    """Barrera de seguridad: solo lectura, solo tablas conocidas, siempre con límite."""
    limpio = sql.strip().rstrip(";")
    if PROHIBIDO.search(limpio):
        return False, "La consulta contiene una operación de escritura."
    if not re.match(r"^\s*(with|select)\b", limpio, re.I):
        return False, "La consulta debe empezar por SELECT o WITH."
    if limpio.count(";") > 0:
        return False, "Solo se permite una sentencia."
    referidas = set(re.findall(r"\b(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*)", limpio, re.I))
    cte = set(re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s+as\s*\(", limpio, re.I))
    desconocidas = referidas - TABLAS_PERMITIDAS - cte
    if desconocidas:
        return False, f"Tablas no permitidas: {', '.join(sorted(desconocidas))}"
    if not re.search(r"\blimit\b", limpio, re.I):
        limpio += "\nLIMIT 200"
    return True, limpio

def consultar(pregunta: str) -> tuple[str, str | None]:
    """Traduce la pregunta a SQL. Devuelve (sql, error)."""
    if not hay_llm():
        return "", "No hay clave de API configurada (ANTHROPIC_API_KEY)."
    try:
        sql = _preguntar(SISTEMA_SQL, pregunta, max_tokens=700)
    except Exception as e:
        return "", f"Error al consultar el modelo: {e}"
    sql = re.sub(r"^```(?:sql)?|```$", "", sql, flags=re.M).strip()
    ok, resultado = validar_sql(sql)
    return (resultado, None) if ok else (sql, resultado)

def resumir_resultado(pregunta: str, sql: str, tabla) -> str:
    """Narra en una frase lo que devolvió la consulta. No recalcula nada."""
    if not hay_llm():
        return ""
    muestra = tabla.head(20).to_markdown(index=False)
    try:
        return _preguntar(
            "Resumís resultados de consultas para un equipo comercial. Máximo 2 frases, en español. "
            "NO calcules nada: describí únicamente lo que muestra la tabla. Si la tabla está vacía, decilo.",
            f"Pregunta: {pregunta}\n\nSQL ejecutado:\n{sql}\n\nResultado:\n{muestra}", max_tokens=250)
    except Exception:
        return ""
