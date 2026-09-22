# Imagem de produção da API do PIQ.
#
# Serve SÓ a API JSON + o PDF do plano. O frontend é um bundle estático
# separado (`frontend/dist/`, ver `docs/deploy.md`) — o backend não o
# serve, e a montagem `/estaticos` foi removida em `T-145`.
#
# Duas etapas: a primeira instala as dependências num ambiente virtual, a
# segunda copia só o resultado. Assim o compilador e os headers de
# desenvolvimento não vão para a imagem final.

# ---------------------------------------------------------------------------
# Etapa 1 — dependências
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS dependencias

# `psycopg[binary]` e `argon2-cffi` compilam extensões nativas na ausência
# de wheel compatível; `libffi-dev` é exigido pelo `cffi` que o WeasyPrint
# usa. Ficam só nesta etapa.
RUN apt-get update && apt-get install --no-install-recommends -y \
        build-essential \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV VIRTUAL_ENV=/opt/venv PATH="/opt/venv/bin:$PATH"
RUN python -m venv "$VIRTUAL_ENV"

# `pyproject.toml` primeiro, sozinho: enquanto ele não mudar, o Docker
# reaproveita a camada de instalação e o build não baixa nada de novo.
COPY pyproject.toml ./
COPY parameters/ ./parameters/
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir ".[app,supabase]"

# ---------------------------------------------------------------------------
# Etapa 2 — imagem final
# ---------------------------------------------------------------------------
FROM python:3.12-slim

# **As bibliotecas nativas do WeasyPrint não são opcionais.** Ele as carrega
# por `cffi` em tempo de execução, então a ausência delas NÃO quebra o build
# nem a subida do container: quebra quando alguém pede o PDF do plano — o
# aluno, no fim do acompanhamento. É exatamente a falha que aparece no
# Windows de desenvolvimento (`cannot load library 'libgobject-2.0-0'`, os 3
# testes pulados da suíte) e a razão de o `HEALTHCHECK` abaixo não bastar
# como garantia: o PDF precisa ser exercitado depois do deploy.
#
# `libpango` traz `libgobject`/`libglib` como dependência, mas as duas estão
# declaradas explicitamente: são elas que o erro nomeia, e quem for depurar
# isso às pressas procura pelo nome do erro, não pela árvore de dependências.
RUN apt-get update && apt-get install --no-install-recommends -y \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libharfbuzz0b \
        libgobject-2.0-0 \
        libglib2.0-0 \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        shared-mime-info \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Usuário sem privilégio: um comprometimento da aplicação não vira root no
# container. Criado antes do COPY para que os arquivos já nasçam dele.
RUN useradd --create-home --shell /usr/sbin/nologin piq

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
COPY --from=dependencias /opt/venv /opt/venv

WORKDIR /app

# Só o que a API precisa em execução. `tests/`, `frontend/`, `plans/`,
# `specs/` e `tasks/` ficam de fora — não são código de produção, e cada
# arquivo a mais é superfície a mais.
COPY --chown=piq:piq app/ ./app/
COPY --chown=piq:piq engine/ ./engine/
COPY --chown=piq:piq collection/ ./collection/
COPY --chown=piq:piq persistencia/ ./persistencia/
COPY --chown=piq:piq report/ ./report/
COPY --chown=piq:piq parameters/ ./parameters/
COPY --chown=piq:piq scripts/ ./scripts/
COPY --chown=piq:piq pyproject.toml ./

USER piq

# A porta é convenção; o provedor normalmente injeta `PORT`. O CMD abaixo
# respeita `$PORT` quando existir.
ENV PORT=8000
EXPOSE 8000

# Sonda de vida do PROCESSO (`/saude`), não do banco. A de banco
# (`/saude/banco`) abre conexão a cada chamada: usada como healthcheck de
# container, marcaria o serviço como morto sempre que o Supabase do free
# tier pausasse — e reiniciar a aplicação não acorda o banco.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,os,sys; sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",8000)}/saude', timeout=4).status==200 else 1)"

# `--proxy-headers` e `--forwarded-allow-ips`: atrás do balanceador do
# provedor, sem eles o Uvicorn vê o IP interno do proxy e monta URLs com
# `http://` mesmo sob HTTPS.
CMD ["sh", "-c", "exec uvicorn app.http.aplicacao:criar_aplicacao --factory --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
