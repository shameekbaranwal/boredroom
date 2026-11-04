"""Answers someone's note to the developer, when a release does what it asked. They alone
see their note and the answer under that release on what's new; with --push it also goes
to their devices, once.

    docker exec boredroom-stage python scripts/reply.py                 the notes, with their numbers
    docker exec boredroom-stage python scripts/reply.py N "answer" [--release ID] [--push]
    docker exec boredroom-stage python scripts/reply.py N --push        push an answer already written
    docker exec boredroom-stage python scripts/reply.py N --clear       take an answer back (unread only)

(production: boredroom.) The release defaults to the latest; it must be out already.
Every answer on production is the developer's own words, approved one by one."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from boredroom import news, reminders  # noqa: E402
from boredroom.config import Config  # noqa: E402
from boredroom.db import make_engine, make_sessionmaker  # noqa: E402
from boredroom.models import Feedback, Person, utcnow  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("note", nargs="?", type=int)
    ap.add_argument("answer", nargs="?")
    ap.add_argument("--release", default=news.LATEST.id)
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--clear", action="store_true")
    a = ap.parse_args()
    cfg = Config()
    tz = ZoneInfo(cfg.default_tz)
    with make_sessionmaker(make_engine(cfg.database_url))() as s:
        if a.note is None:
            for f, who in s.execute(select(Feedback, Person.username).outerjoin(Person, Person.id == Feedback.person_id)
                                    .order_by(Feedback.created_at.desc()).limit(30)).all():
                print(f"#{f.id} · {f.created_at.astimezone(tz):%Y-%m-%d %H:%M} · {f.kind} · {who or 'a former member'}")
                print("    " + f.text.replace("\n", "\n    "))
                if f.reply:
                    print(f"    → answered with {f.reply_release}{'' if f.reply_read_at else ' (unread)'}: {f.reply}")
            return
        f = s.get(Feedback, a.note)
        if f is None or f.person_id is None:
            sys.exit(f"no note #{a.note} from a current member")
        if a.clear:
            if f.reply_read_at:
                sys.exit("they've read it already; it stays")
            f.reply = f.reply_release = f.replied_at = None
            s.commit()
            print(f"#{f.id}: answer taken back")
            return
        if a.answer:
            if a.release not in news.AGE:
                sys.exit(f"no release {a.release} on this server")
            f.reply, f.reply_release, f.replied_at, f.reply_read_at = a.answer.strip(), a.release, utcnow(), None
            s.commit()
            print(f"#{f.id}: answered with {a.release}: {f.reply}")
        if a.push:
            if not f.reply:
                sys.exit(f"#{f.id} has no answer yet")
            if not cfg.push:
                sys.exit("push isn't set up on this server")
            n = reminders.answer(s, f, cfg)
            print(f"#{f.id}: pushed to {n} device{'s' if n != 1 else ''}" if n else f"#{f.id}: no device took it (none, or pushed already)")


if __name__ == "__main__":
    main()
