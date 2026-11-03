"""Reminders: what to push, and the scheduler that pushes it.

Two kinds, both for people with at least one device that takes pushes:
  reset   a game you switched the nudge on for (on your agenda), unfiled, an hour before
          it resets. Games resetting within half an hour of it come along in the same push.
  digest  each board's evening digest, at 20:00 your time, on unless you switch it off:
          what's still open, what the others did, what resets next. Nothing open, no push.

Every push is written to push_log under a key ("reset:krillion:2026-11-01") before it's
sent, and the key is unique per person: a crash mid-send loses a nudge, never doubles one.
"""
from __future__ import annotations

import logging
import random
import threading
import time
from datetime import datetime, timedelta
from typing import Iterator
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from . import reads
from .config import Config
from .models import (Agenda, Board, Membership, Person, PushLog, PushSubscription, Result, SchedulerState, Skip,
                     utcnow)
from .parser import REGISTRY
from .push import Push, Sender, deliver, webpush_sender

log = logging.getLogger(__name__)

LEAD = timedelta(minutes=60)  # a nudge goes out this long before the reset
GROUP = timedelta(minutes=30)  # games resetting this soon after it ride along
DIGEST_AT = 20  # the evening digest's hour, in your timezone; sent in the hour that follows
LOCK = 0x626F7265  # "bore": the scheduler's advisory lock; it's per database, so stage and production don't meet
KEEP = timedelta(days=30)


def _claim(s: Session, person_id: int, kind: str, keys: list[str]) -> list[str]:
    """Writes the log rows; returns the keys that weren't there already."""
    if not keys:
        return []
    got = s.scalars(insert(PushLog).values([{"person_id": person_id, "key": k, "kind": kind, "status": "sending",
                                             "created_at": utcnow()} for k in keys])
                    .on_conflict_do_nothing(index_elements=["person_id", "key"]).returning(PushLog.key)).all()
    s.commit()
    return list(got)


def _mark(s: Session, person_id: int, keys: list[str], status: str) -> None:
    for row in s.scalars(select(PushLog).where(PushLog.person_id == person_id, PushLog.key.in_(keys))):
        row.status = status
    s.commit()


def _left(d: timedelta) -> str:
    m = max(1, round(d.total_seconds() / 60))
    return f"{m}m" if m < 60 else f"{m // 60}h" + (f" {m % 60}m" if m % 60 else "")


def _filed(s: Session, person_id: int, game_id: str, day) -> bool:
    return s.scalar(select(Result.id).where(Result.person_id == person_id, Result.game_id == game_id,
                                            Result.puzzle_day == day, Result.withdrawn_at.is_(None)).limit(1)) is not None


def _skipped(s: Session, person_id: int, game_id: str, day) -> bool:
    return s.get(Skip, (person_id, game_id, day)) is not None


def _pushable(s: Session) -> set[int]:
    return set(s.scalars(select(PushSubscription.person_id).distinct()))


def reset_nudges(s: Session, now: datetime) -> Iterator[tuple[int, list[str], Push]]:
    """(person, log keys, push) for every reset nudge due now."""
    people = _pushable(s)
    if not people:
        return
    rows = s.execute(select(Agenda.person_id, Agenda.game_id, Board.slug).join(
        Membership, (Membership.board_id == Agenda.board_id) & (Membership.person_id == Agenda.person_id)).join(
        Board, Board.id == Agenda.board_id).where(
        Agenda.nudge.is_(True), Membership.left_at.is_(None), Agenda.person_id.in_(people)).order_by(Board.slug)).all()
    games: dict[int, dict[str, str]] = {}  # person -> game -> a board it's on
    for pid, g, slug in rows:
        if g in REGISTRY:
            games.setdefault(pid, {}).setdefault(g, slug)
    for pid, gs in games.items():
        person = s.get(Person, pid)
        open_: list[tuple[datetime, str]] = []
        for g in gs:
            day = reads.game_day(g, person, now)
            if not _filed(s, pid, g, day) and not _skipped(s, pid, g, day):  # sitting it out: no nudge
                open_.append((reads.next_reset(g, person, now), g))
        open_.sort()
        due = [(at, g) for at, g in open_ if at - now <= LEAD]
        if not due:
            continue
        key = lambda g: f"reset:{g}:{reads.game_day(g, person, now).isoformat()}"  # noqa: E731
        # only a game that's due now starts a push; games resetting soon after it ride along
        new = _claim(s, pid, "reset", [key(g) for _, g in due])
        if not new:
            continue
        first = min(at for at, g in due if key(g) in new)
        new += _claim(s, pid, "reset", [key(g) for at, g in open_ if first < at <= first + GROUP and at - now > LEAD])
        picked = [(at, g) for at, g in open_ if key(g) in new]
        names = [REGISTRY[g].name.lower() for _, g in picked]
        at, g = picked[0]
        if len(picked) == 1:
            every = REGISTRY[g].reset.every  # a weekly game's tenure counts weeks
            run, _, risk = reads.tenure(reads._days(s, g, [pid], reads.game_day(g, person, now))[pid],
                                        reads.game_day(g, person, now), every)
            body = (f"your {run}-{'week' if every == 7 else 'day'} tenure lapses at reset." if risk and run >= 2
                    else "you haven't filed. the board is waiting.")
            push = Push(f"{names[0]} resets in {_left(at - now)}", body, f"/b/{gs[g]}", tag="reset")
        else:
            push = Push(f"{len(picked)} items reset within the hour",
                        f"{', '.join(names[:-1])} and {names[-1]}. the meeting started without you.",
                        f"/b/{gs[g]}", tag="reset")
        yield pid, new, push


def digests(s: Session, now: datetime) -> Iterator[tuple[int, list[str], Push]]:
    """(person, log keys, push) for every evening digest due now."""
    people = _pushable(s)
    if not people:
        return
    for m in s.scalars(select(Membership).where(Membership.digest.is_(True), Membership.left_at.is_(None),
                                                Membership.person_id.in_(people))):
        person = m.person
        local = now.astimezone(ZoneInfo(person.tz))
        if local.hour != DIGEST_AT:
            continue
        key = f"digest:{m.board.slug}:{local.date().isoformat()}"
        if not _claim(s, person.id, "digest", [key]):
            continue
        push = digest(s, m, now)
        if push is None:
            _mark(s, person.id, [key], "skipped")
            continue
        yield person.id, [key], push


def digest(s: Session, m: Membership, now: datetime) -> Push | None:
    """One board's evening digest for one member, or None when there's nothing open."""
    # what's open tonight: not a game you're sitting out, nor a weekly one with days to go
    items = [i for i in reads.today(s, m.board, m.person, now)["items"] if not i["skipped"]
             and not (i["weekly"] and not i["filed"] and datetime.fromisoformat(i["resets_at"]) - now > timedelta(days=1))]
    open_ = [i for i in items if not i["filed"]]
    if not open_:
        return None
    done = len(items) - len(open_)
    counts: dict[str, int] = {}
    for i in items:
        for n in i["filed_by"]:
            if n != m.nickname:
                counts[n] = counts.get(n, 0) + 1
    names = [i["name"].lower() for i in open_]
    soon = min(open_, key=lambda i: i["resets_at"])
    left = datetime.fromisoformat(soon["resets_at"]) - now
    title = (f"{m.board.name}: the meeting started without you." if done == 0
             else f"{m.board.name}: {len(open_)} {'item' if len(open_) == 1 else 'items'} still open.")
    others = sorted(counts, key=lambda n: (-counts[n], n))
    said = (f"{others[0]} filed {counts[others[0]]}." if len(others) == 1
            else f"{others[0]} and {others[1]} filed {counts[others[0]] + counts[others[1]]} between them." if len(others) == 2
            else f"{others[0]}, {others[1]} and {len(others) - 2} more filed {sum(counts.values())}." if others
            else "no one else has filed either. a quiet floor.")
    listed = names[0] if len(names) == 1 else f"{', '.join(names[:3])}{' and more' if len(names) > 3 else ''}"
    body = f"{said} open: {listed}. {soon['name'].lower()} resets in {_left(left)}."
    return Push(title, body, f"/b/{m.board.slug}", tag=f"digest:{m.board.slug}")


def tick(s: Session, cfg: Config, now: datetime | None = None, send: Sender = webpush_sender) -> int:
    """One minute's work: every push due now. Returns how many went out."""
    now = now or utcnow()
    sent = 0
    for source in (reset_nudges, digests):
        for pid, keys, push in list(source(s, now)):
            ok = deliver(s, pid, push, cfg, send)
            _mark(s, pid, keys, "sent" if ok else "failed")
            sent += bool(ok)
    st = s.get(SchedulerState, "reminders") or SchedulerState(name="reminders")
    st.last_tick = now
    s.add(st)
    if random.random() < 0.01:
        s.execute(delete(PushLog).where(PushLog.created_at < now - KEEP))
    s.commit()
    return sent


def healthy(s: Session, now: datetime | None = None) -> bool:
    st = s.get(SchedulerState, "reminders")
    return st is not None and (now or utcnow()) - st.last_tick < timedelta(minutes=5)


def start(engine: Engine, cfg: Config) -> threading.Thread:
    """The scheduler: a thread in each gunicorn worker, ticking at the top of every minute.
    Only the worker holding the advisory lock does the work that minute."""
    def loop() -> None:
        while True:
            time.sleep(60 - time.time() % 60 + random.uniform(0.5, 3))
            try:
                with engine.connect() as lock:
                    if not lock.scalar(text("SELECT pg_try_advisory_lock(:k)"), {"k": LOCK}):
                        continue
                    try:
                        with Session(engine, expire_on_commit=False) as s:
                            tick(s, cfg)
                    finally:
                        lock.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": LOCK})
                        lock.commit()
            except Exception:
                log.exception("reminders: the tick failed")
    t = threading.Thread(target=loop, name="reminders", daemon=True)
    t.start()
    return t
