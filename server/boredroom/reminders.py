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

from . import memos, news, reads
from .config import Config
from .models import (Agenda, Board, Feedback, Membership, Memo, Person, PushLog, PushSubscription, Result, SchedulerState, Skip,
                     utcnow)
from .parser import REGISTRY
from .push import Push, Sender, deliver, webpush_sender

log = logging.getLogger(__name__)

EVERY = timedelta(minutes=30)  # the scheduler's tick
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


def _and(xs: list[str]) -> str:
    return xs[0] if len(xs) == 1 else f"{', '.join(xs[:-1])} and {xs[-1]}"


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
        name = lambda g: REGISTRY[g].name.lower()  # noqa: E731
        risks = []  # tenures that lapse if these resets pass unfiled
        for _, g in picked:
            every = REGISTRY[g].reset.every  # a weekly game's tenure counts weeks
            day = reads.game_day(g, person, now)
            run, _, risk = reads.tenure(reads._days(s, g, [pid], day)[pid], day, every)
            if risk and run >= 2:
                risks.append(f"{run}-{'week' if every == 7 else 'day'}" + ("" if len(picked) == 1 else f" {name(g)}"))
        at, g = picked[0]
        if len(picked) == 1:
            title = f"{name(g)} resets in {_left(at - now)}"
            body = f"your {risks[0]} tenure lapses at reset." if risks else "you haven't filed. the board is waiting."
        else:
            # one push for games resetting together: their names up top, each one's time when they differ
            together = len({a for a, _ in picked}) == 1
            names = [name(x) for _, x in picked]
            listed = _and(names)
            title = (f"{listed} reset in {_left(at - now)}" if together and len(names) <= 3
                     else f"{len(picked)} games reset {'in ' + _left(at - now) if together else 'within the hour'}")
            body = ("" if together and len(names) <= 3
                    else ", ".join(f"{name(x)} in {_left(a - now)}" for a, x in picked) + ". ")
            body += (f"your {_and(risks)} {'tenure lapses' if len(risks) == 1 else 'tenures lapse'} at reset." if risks
                     else "none filed yet. the meeting started without you.")
        push = Push(title, body, f"/b/{gs[g]}", tag="reset")
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


NEWS = 45  # a memo this interesting or more can lead the digest
NOT_NEWS = ("pip", "missed", "quorum")  # never the lead: a dig at someone, or no news at all
ABOUT_YOU = ("pb", "tenure", "run", "attendance", "milestone", "fixture", "sweep", "earnings", "commendation")


def _standing(s: Session, m: Membership, now: datetime) -> str | None:
    """Where you stand on the week's daily wins: "you're 2nd this week, 1 win behind athr"."""
    rows = reads.review(s, m.board, m.person, "week", now=now)["standings"]
    mine = next((r for r in rows if r["me"]), None)
    top = [r for r in rows if r["place"] == 1]
    if not top or mine is None:
        return None
    win = lambda n: f"{n} win{'' if n == 1 else 's'}"  # noqa: E731
    if mine["place"] == 1:
        others = [r for r in top if not r["me"]]
        if others:
            return f"you share #1 this week with {_and([r['nickname'] for r in others])}."
        nxt = next((r for r in rows if not r["me"] and r["wins"]), None)
        return f"you hold #1 this week, {win(mine['wins'] - nxt['wins'])} clear of {nxt['nickname']}." if nxt \
            else f"you hold #1 this week on {win(mine['wins'])}, the only one with any."
    if mine["place"] is None:
        return f"{top[0]['nickname']} leads the week on {win(top[0]['wins'])}. you're yet to take one."
    ahead = rows[rows.index(mine) - 1]
    ordinal = {2: "2nd", 3: "3rd"}.get(mine["place"], f"{mine['place']}th")
    return f"you're {ordinal} this week, {win(ahead['wins'] - mine['wins'])} behind {ahead['nickname']}."


def digest(s: Session, m: Membership, now: datetime) -> Push | None:
    """One board's evening digest for one member: the day's news, not a to-do list (the
    reset nudges do that). The biggest memo of the day, where you stand on the week, a line
    about you if there's one, then what's still open. None on a day with nothing to say."""
    board, person = m.board, m.person
    memos.refresh(s, board, person, now)
    today = memos.local_day(person, now)
    rows, nick = memos._visible(s, board, select(Memo).where(Memo.board_id == board.id, Memo.day == today))
    rows.sort(key=lambda x: (-x.interest, x.id))
    lead = next((x for x in rows if x.interest >= NEWS and x.kind not in NOT_NEWS), None)
    yours = next((x for x in rows if x is not lead and person.id in x.subjects and x.kind in ABOUT_YOU), None)
    standing = _standing(s, m, now)
    if not (lead or yours or standing):
        return None
    items = [i for i in reads.today(s, board, person, now)["items"] if not i["skipped"]
             and not (i["weekly"] and not i["filed"] and datetime.fromisoformat(i["resets_at"]) - now > timedelta(days=1))]
    open_ = [i["name"].lower() for i in items if not i["filed"]]
    tail = (f"{len(open_)} still open: {_and(open_[:3]) if len(open_) <= 3 else ', '.join(open_[:3]) + ' and more'}."
            if open_ else "all filed today." if items else "")
    line = lambda x: memos.text(x, nick, person.id).rstrip(".") + "."  # noqa: E731
    body = " ".join(p for p in (lead and line(lead), standing, yours and line(yours), tail) if p)
    weekday = now.astimezone(ZoneInfo(person.tz)).strftime("%A").lower()
    return Push(f"{board.name} · {weekday} so far", body, f"/b/{board.slug}/meeting", tag=f"digest:{board.slug}")


UPDATE_FOR = timedelta(days=3)  # a major release is pushed only while it's fresh
DAYTIME = range(10, 21)  # and only in someone's daytime


def updates(s: Session, now: datetime) -> Iterator[tuple[int, list[str], Push]]:
    """(person, log keys, push) for the latest release, once, if it's major: to everyone with
    reminders on who hasn't read it yet and was here before it, in their daytime, in its
    first few days."""
    r = news.LATEST
    out = datetime.combine(news.day(r), datetime.min.time(), ZoneInfo("UTC"))
    if not r.major or not (out <= now < out + UPDATE_FOR):
        return
    for pid in _pushable(s):
        person = s.get(Person, pid)
        if news.unseen(person) is None or now.astimezone(ZoneInfo(person.tz)).hour not in DAYTIME:
            continue
        if any(f.reply_release == r.id for f in news.replies(s, person)):
            continue  # their answer's own push (scripts/reply.py) tells them about this one
        key = f"update:{r.id}"
        if not _claim(s, pid, "update", [key]):
            continue
        rest = f" and {len(r.notes) - 1} more under what's new." if len(r.notes) > 1 else ""
        yield pid, [key], Push(f"new in boredroom: {r.title}", (r.notes[0] if r.notes else "") + rest, "/news", tag="update")


def answer(s: Session, f: Feedback, cfg: Config, send: Sender = webpush_sender) -> int:
    """The answer to someone's note, pushed to them once, whatever the hour: only ever sent
    by scripts/reply.py, on the developer's word. Returns how many devices took it."""
    if f.person_id is None or not f.reply or f.reply_release not in news.AGE:
        return 0
    r = news.RELEASES[news.AGE[f.reply_release]]
    key = f"reply:{f.id}"
    if not _claim(s, f.person_id, "reply", [key]):
        return 0
    ok = deliver(s, f.person_id, Push(f"re: your {'bug report' if f.kind == 'bug' else 'idea'}", f.reply, f"/news#{r.id}", tag=f"reply:{f.id}")  # its own: two answers both stay in the tray, cfg, send)
    _mark(s, f.person_id, [key], "sent" if ok else "failed")
    return ok


def tick(s: Session, cfg: Config, now: datetime | None = None, send: Sender = webpush_sender) -> int:
    """One tick's work: every push due now. Returns how many went out."""
    now = now or utcnow()
    sent = 0
    for source in (reset_nudges, digests, updates):
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
    return st is not None and (now or utcnow()) - st.last_tick < EVERY + timedelta(minutes=5)


def start(engine: Engine, cfg: Config) -> threading.Thread:
    """The scheduler: a thread in each gunicorn worker, ticking on the hour and half hour
    (utc). Resets fall on whole hours in utc or at someone's midnight, which is a quarter-
    hour boundary anywhere, so a nudge still goes about an hour ahead and every local hour
    gets a tick for the digest. Only the worker holding the advisory lock does the work."""
    def loop() -> None:
        while True:
            step = EVERY.total_seconds()
            time.sleep(step - time.time() % step + random.uniform(0.5, 3))
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
