# Restricted public Risk Service image (aegis.public_app). Never carries demo/exchange credentials.
FROM node:22.11.0-bookworm-slim AS atk
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts

FROM python:3.12.8-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.10.11 /uv /usr/local/bin/uv
COPY --from=atk /usr/local/bin/node /usr/local/bin/node
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY --from=atk /app/node_modules ./node_modules
COPY aegis ./aegis
RUN useradd --create-home --uid 10001 aegis && mkdir -p /data && chown aegis /data
USER aegis
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    AEGIS_SOURCE_MODE=MARKET_ONLY \
    AEGIS_SERVICE_SOURCE_MODE=MARKET_ONLY \
    AEGIS_DB_PATH=/data/aegis.sqlite3
EXPOSE 8080
CMD ["uvicorn", "aegis.public_app:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--no-access-log", "--proxy-headers"]
