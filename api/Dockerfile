# =============================================================================
#  Servicio de reposición de DSMarket
#
#  Por qué existe este fichero: el servicio se probó en un portátil con macOS,
#  Python 3.12 y las versiones que había ese día. «Funciona en mi máquina» no es
#  un plan de despliegue. Esta imagen fija el sistema operativo, el intérprete y
#  las versiones, de modo que lo que corre en el servidor es lo mismo que corrió
#  en las pruebas.
#
#  Construir y ejecutar:
#      docker build -f api/Dockerfile -t dsmarket-api .
#      docker run -p 8000:8000 -v "$PWD/lakehouse:/app/lakehouse:ro" dsmarket-api
#
#  El almacén se monta como volumen y en solo lectura. Es a propósito: la imagen
#  contiene el código, no los datos —que son de la escuela y no se redistribuyen—
#  y el servicio lee, nunca escribe.
# =============================================================================

# Se fija la versión menor del intérprete, no solo la mayor. Entre 3.12 y 3.13
# cambian ruedas de varias dependencias; dejarlo en «3» sería no fijar nada.
FROM python:3.12-slim-bookworm

# Dependencias del sistema. libgomp1 es OpenMP: lightgbm no arranca sin él, y es
# exactamente el mismo error de libomp que aparece en macOS, resuelto de una vez.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Las dependencias primero y el código después: así un cambio en el código no
# invalida la capa de dependencias y la reconstrucción tarda segundos.
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

COPY api/ ./api/
COPY operacion/ ./operacion/

# No ejecutar como root. Cuesta dos líneas y evita la clase entera de problemas
# en que un fallo del servicio se convierte en un fallo del sistema.
RUN useradd --create-home --uid 10001 dsmarket \
 && chown -R dsmarket:dsmarket /app
USER dsmarket

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DSMARKET_MEM=2GB

EXPOSE 8000

# El orquestador de turno necesita saber si el servicio está vivo o solo levantado.
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/salud || exit 1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
