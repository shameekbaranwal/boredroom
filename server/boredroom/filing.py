"""Filing: paste -> parse -> merge with what's already filed -> store.

Results belong to people (one filing counts on every board where that game is on the
person's agenda), so nothing here knows about boards.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .errors import fail
from .models import GameRequest, Paste, Person, PuzzleDay, Result, utcnow
from .parser import REGISTRY, Field, merge, parse
from .parser import Result as Parsed


@dataclass
class Event:
    """What happened to one result in a paste."""
    kind: str  # filed | merged | duplicate | conflict | not_out_yet
    game: str
    puzzle: str
    result_id: int | None = None
    added: list[str] = field(default_factory=list)
    confidence: str = "exact"
    late: bool = False


@dataclass
class Filing:
    paste_id: int
    events: list[Event]
    unknown: list[dict[str, Any]]
    note: str

    def to_dict(self) -> dict[str, Any]:
        return {"paste_id": self.paste_id, "events": [asdict(e) for e in self.events],
                "unknown": self.unknown, "note": self.note}


def key_str(puzzle: int | date | str | None) -> str:
    if isinstance(puzzle, date):
        return puzzle.isoformat()
    return str(puzzle)


def to_parsed(row: Result) -> Parsed:
    """A stored result in the parser's shape, so merge() can compare the two."""
    return Parsed(
        game=row.game_id, puzzle=row.puzzle_key, outcome=row.outcome, metrics=dict(row.metrics),
        fields=[Field(f["name"], f["value"], f["visibility"]) for f in row.fields],
        highlights=list(row.highlights), extras=dict(row.extras), comment=row.comment,
        raw=row.raw, parser=row.parser, confidence=row.confidence, warnings=list(row.warnings),
    )


def _apply(row: Result, r: Parsed) -> None:
    row.outcome = r.outcome
    row.metrics = r.metrics
    row.fields = [{"name": f.name, "value": f.value, "visibility": f.visibility} for f in r.fields]
    row.highlights = r.highlights
    row.extras = r.extras
    row.comment = r.comment
    row.raw = r.raw
    row.confidence = r.confidence
    row.warnings = r.warnings
    row.parser = r.parser


def _puzzle_day(s: Session, person: Person, r: Parsed, key: str, now: datetime) -> date | None:
    game = REGISTRY[r.game]
    day = game.puzzle_day(r.puzzle)
    if day is not None:
        return day
    if game.key != "pair":  # a numbered game with no anchor yet: the day it was filed
        return game.reset.game_day(now, person.tz)
    # a page pair belongs to the day it was first filed (docs/PARSER.md choice 4)
    known = s.get(PuzzleDay, (r.game, key))
    if known:
        return known.day
    day = game.reset.game_day(now, person.tz)
    s.add(PuzzleDay(game_id=r.game, puzzle_key=key, day=day))
    return day


def _find(s: Session, person: Person, game: str, key: str) -> Result | None:
    return s.scalar(select(Result).where(
        Result.person_id == person.id, Result.game_id == game, Result.puzzle_key == key))


def file_paste(s: Session, person: Person, text: str, now: datetime | None = None,
               source: str = "paste") -> Filing:
    now = now or utcnow()
    paste = Paste(person_id=person.id, raw=text, source=source, received_at=now)
    s.add(paste)
    s.flush()
    parsed = parse(text, now=now, tz=person.tz)
    events: list[Event] = []

    for r in parsed.results:
        key = key_str(r.puzzle)[:200]  # the column's width; a page pair can be any length
        ev = Event(kind="filed", game=r.game, puzzle=key, confidence=r.confidence, late=r.status == "late")
        if r.status == "ahead":
            ev.kind = "not_out_yet"
            events.append(ev)
            continue

        row = _find(s, person, r.game, key)
        if row is None:
            row = Result(person_id=person.id, game_id=r.game, puzzle_key=key, late=ev.late,
                         puzzle_day=_puzzle_day(s, person, r, key, now), filed_at=now,
                         paste_ids=[paste.id])
            _apply(row, r)
            s.add(row)
        elif row.withdrawn_at is not None:
            # filing a withdrawn puzzle again brings it back, as an amendment
            _apply(row, r)
            row.withdrawn_at, row.amended_at = None, now
            row.paste_ids = [*row.paste_ids, paste.id]
        else:
            r.puzzle = key
            m = merge(to_parsed(row), r)
            ev.kind = {"enrich": "merged", "duplicate": "duplicate", "conflict": "conflict"}[m.kind]
            ev.added = m.added
            if m.kind == "enrich":
                _apply(row, m.result)
                row.paste_ids = [*row.paste_ids, paste.id]
            elif m.kind == "duplicate":
                row.paste_ids = [*row.paste_ids, paste.id]
        s.flush()
        ev.result_id = row.id
        events.append(ev)

    for u in parsed.unknown:
        s.add(GameRequest(person_id=person.id, name=u.name and u.name[:100], link=u.link and u.link[:200], raw=u.raw))
    return Filing(paste.id, events, [u.to_dict() for u in parsed.unknown], parsed.note)


def replace(s: Session, person: Person, result_id: int, paste_id: int, now: datetime | None = None) -> Result:
    """Answer "replace?" for a conflict: the result from that paste wins."""
    now = now or utcnow()
    row = s.get(Result, result_id)
    paste = s.get(Paste, paste_id)
    if row is None or row.person_id != person.id:
        fail(404, "no such result")
    if paste is None or paste.person_id != person.id:
        fail(404, "no such paste")
    for r in parse(paste.raw, now=paste.received_at, tz=person.tz).results:
        if r.game == row.game_id and key_str(r.puzzle) == row.puzzle_key:
            _apply(row, r)
            row.amended_at, row.withdrawn_at = now, None
            row.paste_ids = [*row.paste_ids, paste.id]
            return row
    fail(400, "that paste has no result for this puzzle")


def withdraw(s: Session, person: Person, result_id: int, now: datetime | None = None) -> Result:
    row = s.get(Result, result_id)
    if row is None or row.person_id != person.id:
        fail(404, "no such result")
    row.withdrawn_at = now or utcnow()
    return row


def result_json(row: Result) -> dict[str, Any]:
    """The owner's full view of a result. Board views filter fields by visibility."""
    return {
        "id": row.id, "game": row.game_id, "name": REGISTRY[row.game_id].name,
        "puzzle": row.puzzle_key, "day": row.puzzle_day.isoformat() if row.puzzle_day else None,
        "outcome": row.outcome, "metrics": row.metrics, "fields": row.fields,
        "highlights": row.highlights, "extras": row.extras, "comment": row.comment,
        "confidence": row.confidence, "warnings": row.warnings, "late": row.late,
        "filed_at": row.filed_at.isoformat(),
        "amended_at": row.amended_at.isoformat() if row.amended_at else None,
        "withdrawn": row.withdrawn_at is not None,
    }
