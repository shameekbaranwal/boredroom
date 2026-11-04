"""What's new: the release notes, newest first, and who has seen the latest.

A release is written here when it's promoted to production; its `id` is the day it went
out ("2026-11-03", or "2026-11-03-2" for a second that day), and the list's order is what
counts. Each person keeps the id of the newest one they've read (`Person.news_seen`), so the
agenda's "what's new" card shows once per release on every device. Someone who joined
after a release never gets its card: it's news only to people who were here before."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from .models import Person


@dataclass(frozen=True)
class Release:
    id: str          # the day it went out: "2026-11-03", "2026-11-03-2" for a second that day
    title: str
    notes: tuple[str, ...] = field(default=())
    major: bool = False  # big enough to tell people about, not only list


RELEASES: tuple[Release, ...] = (
    Release("2026-11-04-4", "your own order", (
        "line up your games the way you play them: in the \"you\" tab, on its \"agenda\" sheet, tap \"arrange\" and move them with ↑ and ↓. the agenda then follows \"my order\", which you can also pick from its sort.",
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
    """They've read up to this release (never moves back)."""
    if release_id in AGE and AGE[release_id] < AGE.get(p.news_seen or "", len(RELEASES)):
        p.news_seen = release_id
