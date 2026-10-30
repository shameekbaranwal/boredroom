"""Alembic environment: the database comes from DATABASE_URL (boredroom.config)."""
from alembic import context

from boredroom import models  # noqa: F401  (registers the tables)
from boredroom.config import Config
from boredroom.db import Base, make_engine

target_metadata = Base.metadata


def run_offline() -> None:
    context.configure(url=Config().database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_online() -> None:
    url = context.config.attributes.get("database_url") or Config().database_url
    with make_engine(url).connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_offline()
else:
    run_online()
