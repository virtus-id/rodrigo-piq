# Backend do PIQ (FastAPI). O frontend tem Dockerfile próprio em frontend/.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# WeasyPrint (PDF do plano) precisa de Pango/HarfBuzz nativos e de ao menos uma fonte.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

# Instalação editável: os pacotes leem dados (registros, templates, parâmetros)
# por caminho relativo ao código, então o código precisa ficar em /app.
# jsonschema: collection/carga.py o importa em runtime, mas o pyproject só o
# declara no extra `dev`. Instalado aqui até o pyproject ser corrigido.
RUN pip install -e ".[app,supabase]" "jsonschema>=4.23"

RUN useradd --create-home --uid 10001 piq && chown -R piq /app
USER piq

EXPOSE 8000

# TLS termina no Nginx Proxy Manager; --proxy-headers respeita o X-Forwarded-*.
# A porta 8000 não é publicada no host: só o container piq-web a alcança.
CMD ["uvicorn", "app.http.aplicacao:criar_aplicacao", "--factory", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips=*"]
