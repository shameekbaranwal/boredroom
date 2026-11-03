"""What's new: the release notes, newest first, and who has seen the latest.

A release is written here when it's promoted to production; its `id` is the day it went
out. Each person keeps the id of the newest one they've read (`Person.news_seen`), so the
agenda's "what's new" card shows once per release on every device. Someone who joined
after a release never gets its card: it's news only to people who were here before."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from .models import Person


@dataclass(frozen=True)
class Release:
    id: str          # the day it went out: "2026-11-03"
    title: str
    notes: tuple[str, ...] = field(default=())
    major: bool = False  # big enough to tell people about, not only list


RELEASES: tuple[Release, ...] = (
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


def unseen(p: Person) -> Release | None:
    """The latest release, if it's news to this person: not read yet, and they were here before it."""
    if p.news_seen is not None and p.news_seen >= LATEST.id:
        return None
    return LATEST if p.created_at.date() < date.fromisoformat(LATEST.id) else None  # joined before the day it went out


def seen(p: Person, release_id: str) -> None:
    """They've read up to this release (never moves back)."""
    if any(r.id == release_id for r in RELEASES) and (p.news_seen is None or release_id > p.news_seen):
        p.news_seen = release_id
