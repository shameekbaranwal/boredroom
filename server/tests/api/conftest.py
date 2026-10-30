"""API tests run against a real Postgres: a throwaway `boredroom_test` database on
the dev server (build/dev-db.sh), migrated with Alembic and emptied after each test."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from boredroom.app import create_app
from boredroom.config import Config
from boredroom.db import Base

SERVER = Path(__file__).resolve().parents[2]
TEST_DB = "boredroom_test"


@pytest.fixture(scope="session")
def engine():
    url = make_url(Config().database_url)
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as c:
            c.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)"))
            c.execute(text(f"CREATE DATABASE {TEST_DB}"))
    except Exception as e:  # no dev database running
        pytest.skip(f"postgres isn't reachable ({e.__class__.__name__}); run build/dev-db.sh")
    test_url = url.set(database=TEST_DB).render_as_string(hide_password=False)
    cfg = AlembicConfig(str(SERVER / "alembic.ini"))
    cfg.set_main_option("script_location", str(SERVER / "migrations"))
    cfg.attributes["database_url"] = test_url
    command.upgrade(cfg, "head")  # the migrations are under test too
    eng = create_engine(test_url)
    yield eng
    eng.dispose()
    with admin.connect() as c:
        c.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)"))
    admin.dispose()


@pytest.fixture
def app(engine):
    app = create_app(engine=engine)
    yield app
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with engine.begin() as c:
        c.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def db(app):
    """A session for calling services directly; closed before the tables are emptied."""
    from sqlalchemy.orm import Session
    s = Session(app.extensions["boredroom.engine"], expire_on_commit=False)
    yield s
    s.rollback()
    s.close()


@pytest.fixture
def person(db):
    from boredroom.models import Person

    def make(name, tz="Asia/Kolkata"):
        p = Person(username=name, tz=tz)
        db.add(p)
        db.commit()
        return p
    return make


@pytest.fixture
def client(app):
    return app.test_client()


class Seat:
    """A guest and their token, with helpers for authed calls."""

    def __init__(self, client, name, tz="Asia/Kolkata"):
        r = client.post("/api/v1/guests", json={"username": name, "tz": tz})
        assert r.status_code == 201, r.json
        self.client, self.name = client, name
        self.headers = {"Authorization": f"Bearer {r.json['token']}"}

    def get(self, path, **kw):
        return self.client.get(f"/api/v1{path}", headers=self.headers, **kw)

    def post(self, path, json=None):
        return self.client.post(f"/api/v1{path}", headers=self.headers, json=json or {})

    def put(self, path, json=None):
        return self.client.put(f"/api/v1{path}", headers=self.headers, json=json or {})

    def patch(self, path, json=None):
        return self.client.patch(f"/api/v1{path}", headers=self.headers, json=json or {})

    def delete(self, path):
        return self.client.delete(f"/api/v1{path}", headers=self.headers)


@pytest.fixture
def seat(client):
    return lambda name, tz="Asia/Kolkata": Seat(client, name, tz)


# 11:30 IST on 30 Oct 2026, the same moment the parser tests use
NOW = datetime(2026, 10, 30, 6, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _forget_invite_misses():
    from boredroom import invites
    invites._misses.clear()
