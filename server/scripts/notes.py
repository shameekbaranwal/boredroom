"""The notes people sent the developer from the app, newest first.

    docker exec boredroom-stage python scripts/notes.py [N]     (production: boredroom)

Read-only: it prints and changes nothing."""
from __future__ import annotations

import sys
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from boredroom.config import Config  # noqa: E402
from boredroom.db import make_engine, make_sessionmaker  # noqa: E402
from boredroom.models import Feedback, Person  # noqa: E402


def main(n: int = 30) -> None:
    cfg = Config()
    tz = ZoneInfo(cfg.default_tz)
    with make_sessionmaker(make_engine(cfg.database_url))() as s:
        rows = s.execute(select(Feedback, Person.username).outerjoin(Person, Person.id == Feedback.person_id)
                         .order_by(Feedback.created_at.desc()).limit(n)).all()
        if not rows:
            print("no notes yet.")
        for f, who in rows:
            where = f" on {f.board}" if f.board else ""
            print(f"{f.created_at.astimezone(tz):%Y-%m-%d %H:%M} · {f.kind} · {who or 'a former member'}{where} · release {f.release}")
            print("    " + f.text.replace("\n", "\n    "))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 30)
