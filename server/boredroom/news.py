"""What's new: the release notes, newest first, and who has seen the latest.

A release is written here when it's promoted to production; its `id` is the day it went
out ("2026-11-03", or "2026-11-03-2" for a second that day), and the list's order is what
counts. Each person keeps the id of the newest one they've read (`Person.news_seen`), so the
agenda's "what's new" card shows once per release on every device. Someone who joined
after a release never gets its card: it's news only to people who were here before.

A release can also answer someone's note (Feedback.reply, written by scripts/reply.py):
that person alone sees their note and the answer under the release, and the card comes
back for them until they've read it."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, object_session

from .models import Feedback, Person, utcnow


@dataclass(frozen=True)
class Release:
    id: str          # the day it went out: "2026-11-03", "2026-11-03-2" for a second that day
    title: str
    notes: tuple[str, ...] = field(default=())
    major: bool = False  # big enough to tell people about, not only list


RELEASES: tuple[Release, ...] = (
    Release("2026-11-04-4", "your own order", (
        "line up your games the way you play them: pick \"my order\" in the agenda's sort, then drag a game by the dots at its left.",
        "or arrange them all at once: in the \"you\" tab, on its \"agenda\" sheet, tap \"arrange\".",
        "and a few small fixes.",
    )),
    Release("2026-11-04-3", "a nudge to update", (
        "a bar at the top now says when there's a new version; \"reload\" gets it.",
    )),
    Release("2026-11-04-2", "reset times on the clock", (
        "prefer \"till 9:30 am\" to \"6h 12m left\"? in the \"you\" tab, on its \"everywhere\" sheet, switch \"reset times\" to \"clock time\". weekly games read \"till midnight on mon\".",
    )),
    Release("2026-11-04", "reminders: the board's evening, and a nudge before a reset", (
        "switch on reminders in the \"you\" tab, on its \"everywhere\" sheet. on android it works right in the browser; on an iphone, add boredroom to your home screen first and switch it on from there.",
        "around 8 pm, one push per board: the day's big news, where you stand this week and what's left to play.",
        "tap a game's bell on the \"agenda\" sheet of the \"you\" tab to get a nudge an hour before it resets whenever you haven't filed it yet. one switch at the top rings every bell.",
        "a game you've skipped stays quiet till it resets, and games resetting together share one push.",
        "the \"you\" tab has a third sheet, \"agenda\", so the board's settings aren't buried under its games.",
        "and a few small fixes.",
    ), major=True),
    Release("2026-11-03", "what's new, and a word with the developer", (
        "this page: what changed in each release. a card on your agenda says when there's something new.",
        "send the developer a note, a bug or an idea: you → everywhere → send a note.",
    ), major=True),
    Release("2026-11-02", "the week before, in short", (
        "tap anyone's name for their page on the board: what they play, their tenure, wins, best and last results.",
        "skip a game till it resets: open its row on the agenda, then \"skip till reset\".",
        "weekly games: the travle challenge counts by the week.",
        "no signal? the app shows your last copy, and a result you paste waits on your phone until it can be filed.",
        "\"send on\" for a spoiler result keeps the spoiler folded under \"read more\".",
        "a filed game links to its own site.",
    )),
)
LATEST = RELEASES[0]


def release_json(r: Release) -> dict[str, Any]:
    return {"id": r.id, "title": r.title, "notes": list(r.notes), "major": r.major}


AGE = {r.id: n for n, r in enumerate(RELEASES)}  # 0 is the newest


def day(r: Release) -> date:
    return date.fromisoformat(r.id[:10])


def unseen(p: Person) -> Release | None:
    """The latest release, if it's news to this person: not read yet, and they were here before it."""
    if AGE.get(p.news_seen or "") == 0:
        return None
    return LATEST if p.created_at.date() < day(LATEST) else None  # joined before the day it went out


def seen(p: Person, release_id: str) -> None:
    """They've read up to this release (never moves back), and the answers to their notes
    that came with it or before it."""
    if release_id not in AGE:
        return
    if AGE[release_id] < AGE.get(p.news_seen or "", len(RELEASES)):
        p.news_seen = release_id
    if s := object_session(p):
        for f in replies(s, p):
            if f.reply_read_at is None and AGE[f.reply_release] >= AGE[release_id]:
                f.reply_read_at = utcnow()


def replies(s: Session, p: Person) -> list[Feedback]:
    """Their notes the developer has answered, with a release that's out, newest first."""
    rows = s.scalars(select(Feedback).where(Feedback.person_id == p.id, Feedback.reply.is_not(None),
                                            Feedback.reply_release.in_(list(AGE))))
    return sorted(rows, key=lambda f: AGE[f.reply_release])


def reply_json(f: Feedback) -> dict[str, Any]:
    return {"release": f.reply_release, "kind": f.kind, "text": f.text, "reply": f.reply, "read": f.reply_read_at is not None}


def card(p: Person) -> dict[str, Any] | None:
    """The agenda's "what's new" card: the latest release while it's news to them, or the
    release that answered one of their notes, until they've read the answer."""
    s = object_session(p)
    unread = [f for f in replies(s, p) if f.reply_read_at is None] if s else []
    r = unseen(p) or (RELEASES[AGE[unread[0].reply_release]] if unread else None)
    if r is None:
        return None
    mine = next((f for f in unread if f.reply_release == r.id), None)
    return release_json(r) | ({"for_you": mine.reply} if mine else {})
