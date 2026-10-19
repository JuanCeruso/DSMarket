# -*- coding: utf-8 -*-
"""
La política de reposición, sin datos alrededor.

Estas seis funciones son las que deciden cuánto stock se pide. Estaban dentro de `reposicion.py`,
mezcladas con la consulta al almacén, y por eso no se podían probar: comprobar que el stock de
seguridad crece con el nivel de servicio exigía reconstruir 163 MB de almacén.

Separarlas no cambia ningún número. Cambia que ahora hay veinte pruebas que se ejecutan en tres
segundos y que se disparan si alguien toca la fórmula. Es la diferencia entre creer que la
política es correcta y saberlo cada vez que se hace un commit.
"""
from __future__ import annotations
import numpy as np
from scipy.stats import norm

# Nivel de servicio objetivo (Tarea 4, secciones 5.1 y 7): lo decide la merma, no el segmento.
# Lo fresco (SUPERMARKET) se queda en el 90%; lo no perecedero, cuyo sobrante se vende la semana
# siguiente, al 95%. Son parámetros de negocio: cuando DSMarket mida la merma real se ajustan aquí.
NIVEL_POR_CATEGORIA = {"SUPERMARKET": .90, "ACCESORIES": .95, "HOME_&_GARDEN": .95}
NIVEL_POR_DEFECTO = 0.95     # categoría no perecedera: el valor de HOME_&_GARDEN y ACCESORIES
ALFA_CUANTIL = 0.90          # el cuantil que predice el modelo p90


def razon_critica(coste_quiebre: float, coste_sobrante: float) -> float:
    """Nivel de servicio óptimo del vendedor de periódicos: tau* = Cu / (Cu + Co).

    Es el resultado que convierte «¿qué nivel de servicio ponemos?» de una decisión de despacho
    en una cuenta. El 0,90 uniforme del proyecto no sale de aquí: sale de la costumbre. El
    experimento 05 midió lo que cuesta esa costumbre.
    """
    if coste_quiebre < 0 or coste_sobrante < 0:
        raise ValueError("los costes no pueden ser negativos")
    total = coste_quiebre + coste_sobrante
    if total <= 0:
        raise ValueError("al menos uno de los dos costes tiene que ser positivo")
    return coste_quiebre / total


def nivel_servicio(item: str) -> float:
    """Nivel objetivo según la categoría del producto (el prefijo del código de artículo)."""
    categoria = item.rsplit("_", 2)[0] if item.count("_") >= 2 else item
    return NIVEL_POR_CATEGORIA.get(categoria, NIVEL_POR_DEFECTO)


def sigma_desde_cuantil(p90: np.ndarray, media: np.ndarray, alfa: float = ALFA_CUANTIL) -> np.ndarray:
    """Desvío implícito en la distancia entre el cuantil predicho y la media predicha.

    Supone normalidad local, que es un supuesto y se declara: sigma = (q_alfa - media) / z_alfa.
    La distancia nunca es negativa —`predecir.py` impone la monotonía al escribir—, pero se
    recorta igual por si estas funciones se usan sobre predicciones de otra procedencia.
    """
    distancia = np.maximum(np.asarray(p90, float) - np.asarray(media, float), 0.0)
    return distancia / norm.ppf(alfa)


def agregar_sigma(sigma_diario: np.ndarray, dias: int) -> np.ndarray:
    """Desvío de la suma de `dias` días a partir del desvío diario: la raíz de la suma de cuadrados.

    Vale bajo independencia entre días. En demanda minorista hay autocorrelación semanal, de modo
    que esto **subestima** el desvío real; el efecto se compensa en parte porque el modelo
    cuantílico ya la ve. Queda anotado porque es el supuesto más discutible de la política.
    """
    if dias < 1:
        raise ValueError("la ventana de cobertura tiene que ser de al menos un día")
    return np.asarray(sigma_diario, float) * np.sqrt(dias)


def stock_seguridad(sigma: np.ndarray, nivel: np.ndarray) -> np.ndarray:
    """z(nivel) * sigma, nunca negativo."""
    z = norm.ppf(np.clip(np.asarray(nivel, float), 1e-6, 1 - 1e-6))
    return np.maximum(z * np.asarray(sigma, float), 0.0)


def nivel_objetivo(demanda_esperada: np.ndarray, sigma: np.ndarray, nivel: np.ndarray) -> np.ndarray:
    """El nivel S de una política (R, S): demanda del ciclo más colchón.

    El pedido es S menos lo que haya en stock, y esa resta ocurre fuera: el sistema no conoce el
    stock. Aquí se calcula la parte que sí depende de los datos.
    """
    return np.maximum(np.asarray(demanda_esperada, float), 0.0) + stock_seguridad(sigma, nivel)


def coste_esperado(objetivo: np.ndarray, demanda: np.ndarray,
                   coste_quiebre: float, coste_sobrante: float) -> np.ndarray:
    """Coste del vendedor de periódicos de un nivel frente a una demanda observada.

    Es, término a término, `(Cu + Co)` por la pérdida pinball evaluada en tau*. Esa identidad es
    la que justifica elegir el modelo por coste y no por RMSE: la métrica de negocio y la función
    de pérdida del modelo cuantílico son, salvo una constante, la misma función.
    """
    objetivo = np.asarray(objetivo, float)
    demanda = np.asarray(demanda, float)
    falta = np.maximum(demanda - objetivo, 0.0)
    sobra = np.maximum(objetivo - demanda, 0.0)
    return coste_quiebre * falta + coste_sobrante * sobra


def pinball(y: np.ndarray, pred: np.ndarray, tau: float) -> np.ndarray:
    """Pérdida pinball término a término, con la convención habitual."""
    y, pred = np.asarray(y, float), np.asarray(pred, float)
    d = y - pred
    return np.maximum(tau * d, (tau - 1) * d)


# --------------------------------------------------------------------------- política híbrida
VENTANA_HISTORIA = 180       # días de historia que se usan para el percentil empírico


def completar_ventana(valores: np.ndarray, cobertura: int) -> np.ndarray:
    """Devuelve exactamente `cobertura` días por serie (último eje).

    Si el horizonte predicho termina antes de que acabe la cobertura —la última revisión de un
    horizonte de 28 días cubre 9 días y solo quedan 7 predichos—, los días que faltan se rellenan
    con la media de los últimos 7 días disponibles. Sin esto, esa revisión cubriría menos días de
    los que debe y su nivel objetivo saldría bajo.
    """
    v = np.asarray(valores, float)
    if v.shape[-1] >= cobertura:
        return v[..., :cobertura]
    falta = cobertura - v.shape[-1]
    relleno = np.repeat(v[..., -7:].mean(axis=-1, keepdims=True), falta, axis=-1)
    return np.concatenate([v, relleno], axis=-1)


def percentil_empirico(historia: np.ndarray, cobertura: int, nivel) -> np.ndarray:
    """Percentil `nivel` de las ventas acumuladas en ventanas móviles de `cobertura` días.

    `historia` es una matriz (series x días) con las ventas recientes. Es la regla de las series
    estables (clase X): con mucho volumen y comportamiento regular, el histórico bruto estima el
    nivel necesario mejor que el modelo (Tarea 4, sección 6). `nivel` es un escalar o un vector
    con un nivel por serie.
    """
    h = np.atleast_2d(np.asarray(historia, float))
    ventanas = np.lib.stride_tricks.sliding_window_view(h, cobertura, axis=1).sum(axis=2)
    niveles = np.broadcast_to(np.asarray(nivel, float), (h.shape[0],))
    salida = np.empty(h.shape[0])
    for n in np.unique(niveles):
        k = niveles == n
        salida[k] = np.percentile(ventanas[k], n * 100, axis=1)
    return salida


def nivel_hibrido(demanda: np.ndarray, sigma: np.ndarray, nivel: np.ndarray,
                  es_x: np.ndarray, empirico: np.ndarray) -> np.ndarray:
    """Nivel objetivo de la política híbrida (Tarea 4, sección 7).

    Series estables (clase X): percentil empírico del histórico. Series variables y erráticas
    (clases Y y Z): demanda predicha más stock de seguridad del modelo cuantílico.
    """
    return np.where(np.asarray(es_x, bool), empirico, nivel_objetivo(demanda, sigma, nivel))
