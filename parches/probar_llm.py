# -*- coding: utf-8 -*-
"""
Diagnóstico de la capa de lenguaje natural.

`hay_llm()` devuelve False por cuatro motivos posibles y no dice cuál. Este script los comprueba
uno a uno y, si todos pasan, hace **una** llamada mínima a la API para confirmar que la clave y
el modelo funcionan de verdad.

    python3 parches/probar_llm.py

Ejecutar desde PROYECTO/, con el mismo entorno con el que se arranca la aplicación. Si aquí sale
todo en verde y en la app sigue sin funcionar, el problema es que Streamlit se está lanzando
desde otra terminal o con otro entorno.
"""
from __future__ import annotations
import os, sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "app"))

VERDE, ROJO, FIN = "\033[32m", "\033[31m", "\033[0m"


def ok(t):
    print(f"  {VERDE}[ ok ]{FIN} {t}")


def mal(t, arreglo):
    print(f"  {ROJO}[FALLA]{FIN} {t}")
    for linea in arreglo.strip().split("\n"):
        print(f"         {linea}")


def main():
    print("\nDIAGNÓSTICO DE LA CAPA DE LENGUAJE\n" + "-" * 66)
    print(f"  intérprete: {sys.executable}\n")
    fallos = 0

    # ---------- 0. qué proveedor está configurado ----------
    try:
        from explicador import CFG
        multi = True
    except ImportError:
        CFG, multi = {"proveedor": "anthropic", "familia": "anthropic",
                      "var_clave": "ANTHROPIC_API_KEY", "necesita_clave": True,
                      "base_url": None}, False
    except Exception:
        CFG, multi = {"proveedor": "anthropic", "familia": "anthropic",
                      "var_clave": "ANTHROPIC_API_KEY", "necesita_clave": True,
                      "base_url": None}, False
    print(f"  proveedor : {CFG['proveedor']}"
          + ("" if multi else "   (capa de un solo proveedor: sin el parche multiproveedor)"))
    if CFG.get("base_url"):
        print(f"  extremo   : {CFG['base_url']}")
    print()

    # ---------- 1. la biblioteca ----------
    paquete = "anthropic" if CFG["familia"] == "anthropic" else "openai"
    try:
        lib = __import__(paquete)
        ok(f"biblioteca «{paquete}» instalada (versión {getattr(lib, '__version__', '?')})")
    except ImportError:
        fallos += 1
        mal(f"la biblioteca «{paquete}» no está instalada en este entorno",
            f"pip install {paquete}\n"
            "Ojo: tiene que ser el MISMO entorno con el que arrancás Streamlit.")

    # ---------- 2. la clave ----------
    var = CFG.get("var_clave")
    if not CFG.get("necesita_clave", True):
        ok(f"el proveedor «{CFG['proveedor']}» no necesita clave")
        clave = ""
    else:
        clave = os.environ.get(var, "")
        if not clave:
            fallos += 1
            mal(f"la variable {var} no está definida en este shell",
                f'export {var}="..."\n'
                "Se pierde al cerrar la terminal: para que persista, añadila a ~/.zshrc.")
        elif var == "ANTHROPIC_API_KEY" and not clave.startswith("sk-ant-"):
            fallos += 1
            mal(f"la clave no tiene el formato esperado (empieza por «{clave[:7]}…»)",
                "Una clave de la API de Anthropic empieza por sk-ant-.")
        else:
            ok(f"clave presente en {var} ({len(clave)} caracteres, termina en …{clave[-4:]})")

    # ---------- 3. lo que ve el módulo ----------
    try:
        from explicador import hay_llm, MODELO
        estado = hay_llm()
        if estado:
            ok("hay_llm() devuelve True")
        else:
            fallos += 1
            mal("hay_llm() devuelve False",
                "Si los dos puntos anteriores están en verde: con Ollama, comprobá que el\n"
                "servidor esté levantado (ollama serve). En otro caso, el módulo se está\n"
                "importando desde un entorno distinto del que estás usando ahora.")
        print(f"         modelo configurado: {MODELO}")
    except Exception as e:
        fallos += 1
        mal(f"no se pudo importar app/explicador.py: {e}",
            "Ejecutá este script desde la carpeta PROYECTO/.")
        MODELO = None

    if fallos:
        print(f"\n  {fallos} comprobación(es) fallida(s). No se intenta la llamada.\n")
        return 1

    # ---------- 4. la llamada real ----------
    print("\n  probando una llamada mínima…")
    try:
        from explicador import _preguntar
        texto = _preguntar("Respondé con una sola palabra.",
                           "Decí: listo", max_tokens=20)
        ok(f"el modelo respondió: «{texto}»")
        print(f"         proveedor: {CFG['proveedor']} · modelo: {MODELO}")
        print(f"\n  {VERDE}Todo en verde.{FIN} Arrancá la app DESDE ESTA MISMA TERMINAL:\n")
        print("      streamlit run app/inicio.py\n")
        return 0
    except Exception as e:
        texto = str(e)
        print()
        if "authentication" in texto.lower() or "401" in texto or "invalid x-api-key" in texto.lower():
            mal("la clave fue rechazada",
                "La clave no es válida o fue revocada. Generá una nueva en la consola.")
        elif "not_found" in texto.lower() or "404" in texto or "model" in texto.lower():
            mal(f"el modelo «{MODELO}» no existe o no está disponible para tu cuenta",
                'export DSMARKET_LLM_MODELO="claude-sonnet-5"\n'
                "y volvé a probar. Los identificadores de modelo cambian con el tiempo.")
        elif "connection" in texto.lower() or "refused" in texto.lower():
            mal("no se pudo conectar con el extremo",
                "Con Ollama: comprobá que el servidor esté corriendo con «ollama serve»\n"
                "y que el modelo esté descargado con «ollama list».")
        elif "credit" in texto.lower() or "billing" in texto.lower() or "quota" in texto.lower():
            mal("la cuenta no tiene saldo",
                "La API se paga aparte de cualquier suscripción. Cargá crédito en la consola.")
        elif "rate" in texto.lower() or "429" in texto:
            mal("límite de velocidad alcanzado", "Esperá un minuto y volvé a probar.")
        else:
            mal("la llamada falló", texto[:400])
        return 1


if __name__ == "__main__":
    sys.exit(main())
