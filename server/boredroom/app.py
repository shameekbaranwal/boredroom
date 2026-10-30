"""The Flask app: `create_app()` for gunicorn (boredroom.app:create_app()) and tests."""
from __future__ import annotations

from flask import Flask, g
from sqlalchemy.engine import Engine

from . import errors
from .api import api
from .config import Config
from .db import make_engine, make_sessionmaker


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
    return app
