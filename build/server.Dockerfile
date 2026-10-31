# The boredroom app: the Flask API, serving the built web app, under gunicorn on 5077.
# Build context is the repo root (it needs server/ and web/). Migrations run on boot.

FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.10.8 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/venv PATH="/venv/bin:$PATH" \
    BOREDROOM_WEB_DIST=/app/web
# dependencies first so this layer caches across code changes
COPY server/pyproject.toml server/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY server/boredroom ./boredroom
COPY server/migrations ./migrations
COPY server/alembic.ini ./
COPY server/scripts ./scripts
COPY --from=web /web/dist ./web
# never root: a hole in the app can't touch the image or the volume mounts as root
RUN useradd --system --uid 10001 --no-create-home boredroom
USER boredroom
EXPOSE 5077
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5077/health')" || exit 1
CMD ["sh", "-c", "alembic upgrade head && exec gunicorn --bind 0.0.0.0:5077 --workers 2 --timeout 15 --access-logfile - 'boredroom.app:create_app()'"]
