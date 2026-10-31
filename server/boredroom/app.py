"""The Flask app: `create_app()` for gunicorn (boredroom.app:create_app()) and tests."""
from __future__ import annotations

from pathlib import Path

from flask import Flask, Response, g, request, send_from_directory
from sqlalchemy.engine import Engine

from . import errors, invites, preview
from .api import api
from .config import Config
from .db import make_engine, make_sessionmaker
from .errors import fail
from .legal import legal


# What the page may load: itself, Google sign-in, Google Fonts. No inline scripts, no
# plugins, never framed. Inline styles stay allowed (React's style={} attributes).
CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self' https://accounts.google.com/gsi/client",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://accounts.google.com/gsi/style",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data: https://*.googleusercontent.com",
    "frame-src https://accounts.google.com/gsi/",
    "connect-src 'self' https://accounts.google.com/gsi/",
    "worker-src 'self'", "manifest-src 'self'",
    "object-src 'none'", "base-uri 'none'", "form-action 'self'", "frame-ancestors 'none'",
])
HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    "Strict-Transport-Security": "max-age=31536000",
    # google's sign-in popup needs to talk back to its opener
    "Cross-Origin-Opener-Policy": "same-origin-allow-popups",
}


def _secure(resp: Response) -> Response:
    for k, v in HEADERS.items():
        resp.headers.setdefault(k, v)
    if resp.mimetype == "text/html":
        resp.headers.setdefault("Content-Security-Policy", CSP)
    if request.path.startswith("/api/"):  # personal data: never kept by a browser or proxy
        resp.headers.setdefault("Cache-Control", "no-store")
    return resp


def create_app(config: Config | None = None, engine: Engine | None = None) -> Flask:
    config = config or Config()
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = config.max_paste_bytes
    app.config["BOREDROOM"] = config
    app.after_request(_secure)
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

    page = (dist / "index.html").read_text(encoding="utf-8")

    @app.get("/og/<name>.png")
    def card(name: str):
        if name not in preview.CARDS:
            return send_from_directory(dist, "og.png")
        resp = Response(preview.generic_card(name), mimetype="image/png")
        resp.cache_control.max_age = 86400
        return resp

    @app.get("/og/invite/<code>.png")
    def invite_card(code: str):
        inv = invites.peek(g.db, code)
        if inv is None:
            return send_from_directory(dist, "og.png")
        resp = Response(preview.invite_png(inv), mimetype="image/png")
        resp.cache_control.max_age = 3600
        return resp

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
        # the app routes itself; the page only differs in its link-preview tags
        inv = invites.peek(g.db, path.removeprefix("join/")) if path.startswith("join/") else None
        resp = Response(preview.tags(page, f"https://{request.host}", inv), mimetype="text/html")
        resp.cache_control.no_cache = True
        return resp
