# TEMPORARY: the early parser demo (server/demo/, Flask under gunicorn), shared with
# friends while the real web app is built. It goes away when the app lands; see
# build/README.md. Build context is server/.
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.10.8 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/venv PATH="/venv/bin:$PATH"
# dependencies first so this layer caches across code changes
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY boredroom ./boredroom
COPY demo ./demo
EXPOSE 5077
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5077/health')" || exit 1
CMD ["gunicorn", "--bind", "0.0.0.0:5077", "--workers", "2", "--access-logfile", "-", "demo.app:app"]
