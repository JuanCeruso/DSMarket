# -*- coding: utf-8 -*-
"""
Parche: la capa de lenguaje deja de depender de un proveedor concreto.

POR QUÉ
-------
`explicador.py` llamaba directamente al SDK de Anthropic. Eso ata el proyecto a un proveedor de
pago y, sobre todo, obliga a que haya conexión durante la demostración. Ninguna de las dos cosas
es deseable en un sistema que decide compras para una cadena minorista.

Casi todos los proveedores —y Ollama en local— exponen hoy una interfaz compatible con la de
OpenAI, así que basta con una capa de adaptación de treinta líneas para que el proveedor sea una
**variable de entorno** y no una decisión de código.

CÓMO SE ELIGE PROVEEDOR
-----------------------
    export DSMARKET_LLM=ollama       # local, gratis, sin clave  <- el recomendado
    export DSMARKET_LLM=groq         # nube, plan gratuito, muy rápido
    export DSMARKET_LLM=gemini       # nube, plan gratuito
    export DSMARKET_LLM=openrouter   # nube, modelos marcados :free
    export DSMARKET_LLM=anthropic    # de pago, es lo que había

Cada preajuste trae su URL y su modelo por defecto; los dos se pueden pisar con
`DSMARKET_LLM_BASE_URL` y `DSMARKET_LLM_MODELO`. Si no se define ninguno, se mantiene el
comportamiento anterior: Anthropic si hay `ANTHROPIC_API_KEY`, y explicación por reglas si no.

    python3 parches/aplicar_llm_multiproveedor.py
    python3 parches/aplicar_llm_multiproveedor.py --revisar
"""
from __future__ import annotations
import argparse, os, re, shutil, sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FICHERO = os.path.join(RAIZ, "app", "explicador.py")

INICIO = "def hay_llm() -> bool:"
FIN = "    return respuesta.content[0].text.strip()"

BLOQUE = '''# --------------------------------------------------------------- proveedor
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
    return respuesta.choices[0].message.content.strip()'''


def main(revisar):
    if not os.path.exists(FICHERO):
        sys.exit(f"No encuentro {FICHERO}. Ejecutá este parche desde la carpeta PROYECTO/.")
    s = open(FICHERO, encoding="utf-8").read()

    if "PREAJUSTES = {" in s:
        print("El parche ya está aplicado. No se toca nada.")
        return

    i = s.find(INICIO)
    j = s.find(FIN)
    if i < 0 or j < 0 or j < i:
        sys.exit("No encuentro el bloque esperado en app/explicador.py. "
                 "Si lo editaste a mano, aplicá el cambio manualmente: el bloque nuevo está en "
                 "la constante BLOQUE de este fichero, y sustituye desde 'def hay_llm' hasta el "
                 "final de '_preguntar'.")
    j += len(FIN)

    # la línea de MODELO se vuelve redundante: la define el bloque nuevo
    nuevo = re.sub(r"^MODELO = os\.environ\.get\([^\n]*\)\n", "", s[:i], flags=re.M) \
            + BLOQUE + s[j:]

    print("  bloque localizado en app/explicador.py")
    if revisar:
        print("  (--revisar: no se ha modificado nada)")
        return

    shutil.copy2(FICHERO, FICHERO + ".bak_proveedor")
    open(FICHERO, "w", encoding="utf-8").write(nuevo)
    import py_compile
    py_compile.compile(FICHERO, doraise=True)

    print("""
  aplicado · copia de seguridad en app/explicador.py.bak_proveedor

  Elegí proveedor con una variable de entorno:

      export DSMARKET_LLM=ollama       # local, gratis, sin clave
      export DSMARKET_LLM=groq         # nube, plan gratuito
      export DSMARKET_LLM=gemini       # nube, plan gratuito
      export DSMARKET_LLM=anthropic    # de pago

  Y comprobá con:  python3 parches/probar_llm.py""")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--revisar", action="store_true", help="comprobar sin modificar")
    a = ap.parse_args()
    main(a.revisar)
