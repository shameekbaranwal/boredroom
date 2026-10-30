"""The Flask app: `create_app()` for gunicorn (boredroom.app:create_app()) and tests."""
from __future__ import annotations

from pathlib import Path

from flask import Flask, g, send_from_directory
from sqlalchemy.engine import Engine

from . import errors
from .api import api
from .config import Config
from .db import make_engine, make_sessionmaker
from .errors import fail
from .legal import legal


def create_app(config: Config | None = None, engine: Engine | None = None) -> Flask:
    config = config or Config()
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = config.max_paste_bytes
    app.config["BOREDROOM"] = config
    engine = engine or make_engine(config.database_url)
    Session = make_sessionmaker(engine)
    app.extensions["boredroom.engine"] = engine

    @app.before_request
    def _open_session():
        g.db = Session()

    @app.teardown_request
    def _close_session(exc):
        db = g.pop("db", None)
        if db is not None:
            if exc is not None:
                db.rollback()
            db.close()

    @app.get("/health")
    def health():
        return {"ok": True}

    errors.register(app)
    app.register_blueprint(api)
    app.register_blueprint(legal)
    _serve_web(app, Path(config.web_dist))
    return app


def _serve_web(app: Flask, dist: Path) -> None:
    """The built web app: real files as they are, every other path gets index.html
    (the app routes itself). Skipped when there's no build, as in the API tests."""
    if not (dist / "index.html").is_file():
        return

    @app.get("/", defaults={"path": ""})
    @app.get("/<path:path>")
    def web(path: str):
        if path.startswith("api/"):
            fail(404, "no such endpoint")
        f = (dist / path).resolve()
        if path and f.is_file() and f.is_relative_to(dist.resolve()):
            resp = send_from_directory(dist, path)
            if path.startswith("assets/"):  # hashed names: cache for good
                resp.cache_control.max_age, resp.cache_control.immutable = 31536000, True
            return resp
        resp = send_from_directory(dist, "index.html")
        resp.cache_control.no_cache = True
        return resp
