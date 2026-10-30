"""Board reads: today's agenda and one puzzle's minutes (docs/SERVER.md part 4).

Everything is computed per request. Visibility is enforced here: detail and spoiler
fields, the raw paste and extras only reach someone who has filed that puzzle."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from .filing import to_parsed
from .models import Agenda, Board, Membership, Person, Result, utcnow
from .parser import REGISTRY
from .parser.rank import rank


def game_day(game_id: str, viewer: Person, now: datetime) -> date:
    return REGISTRY[game_id].reset.game_day(now, viewer.tz)


def next_reset(game_id: str, viewer: Person, now: datetime) -> datetime:
    reset = REGISTRY[game_id].reset
    tz = ZoneInfo(reset.tz or viewer.tz)
    local = now.astimezone(tz)
    at = local.replace(hour=reset.at.hour, minute=reset.at.minute, second=0, microsecond=0)
    if at <= local:
        at = (at.replace(tzinfo=None) + timedelta(days=1)).replace(tzinfo=tz)
    return at


def _players(s: Session, board: Board, game_id: str) -> list[Membership]:
    """Members who have the game on their agenda here."""
    return list(s.scalars(
        select(Membership).join(Agenda, (Agenda.board_id == Membership.board_id)
                                & (Agenda.person_id == Membership.person_id))
        .where(Membership.board_id == board.id, Membership.left_at.is_(None), Agenda.game_id == game_id)))


def _results(s: Session, game_id: str, day: date, people: list[int]) -> list[Result]:
    if not people:
        return []
    return list(s.scalars(select(Result).where(
        Result.game_id == game_id, Result.puzzle_day == day, Result.person_id.in_(people),
        Result.withdrawn_at.is_(None))))


def _placed(rows: list[Result]) -> list[tuple[int, Result]]:
    """[(place, row)] for one game's results; 0 means unranked."""
    parsed = [to_parsed(r) for r in rows]
    row_of = {id(p): r for p, r in zip(parsed, rows)}
    return [(place, row_of[id(p)]) for place, p in rank(parsed)]


def _place_label(placed: list[tuple[int, Result]], place: int) -> str:
    if place == 0:
        return ""
    tied = sum(1 for p, _ in placed if p == place) > 1
    return f"={place}" if tied else str(place)


def result_view(row: Result, nickname: str, place: str, open_: bool, me: bool) -> dict[str, Any]:
    """One row of the minutes. `open_`: the viewer has filed this puzzle."""
    full = open_ or me
    return {
        "id": row.id if me else None, "nickname": nickname, "me": me, "place": place,
        "puzzle": row.puzzle_key, "outcome": row.outcome, "metrics": row.metrics,
        "highlights": row.highlights, "late": row.late, "amended": row.amended_at is not None,
        "fields": [f for f in row.fields if full or f["visibility"] == "public"],
        "hidden": 0 if full else sum(f["visibility"] != "public" for f in row.fields),
        "comment": row.comment if full else "",
        "raw": row.raw if full else None,
        "filed_at": row.filed_at.isoformat(),
    }


def today(s: Session, board: Board, viewer: Person, now: datetime | None = None) -> dict[str, Any]:
    now = now or utcnow()
    games = list(s.scalars(select(Agenda.game_id).where(
        Agenda.board_id == board.id, Agenda.person_id == viewer.id)))
    items = []
    for g in games:
        game = REGISTRY[g]
        day = game_day(g, viewer, now)
        players = _players(s, board, g)
        nick = {m.person_id: m.nickname for m in players}
        rows = _results(s, g, day, list(nick))
        placed = _placed(rows)
        mine = next((r for r in rows if r.person_id == viewer.id), None)
        top = [r for p, r in placed if p == 1]
        my_place = next((_place_label(placed, p) for p, r in placed if r is mine), "")
        current = game.current(now, viewer.tz)
        items.append({
            "game": g, "name": game.name, "ranked": game.ranked(), "links": list(game.links),
            "day": day.isoformat(),
            "puzzle": mine.puzzle_key if mine else (str(current.isoformat() if isinstance(current, date)
                                                       else current) if current is not None else None),
            "resets_at": next_reset(g, viewer, now).isoformat(),
            "filed": mine is not None,
            "place": my_place,
            "present": len(rows), "players": len(players),
            "filed_by": sorted(nick[r.person_id] for r in rows),
            "leader": ({"nickname": nick[top[0].person_id] if len(top) == 1 else None,
                        "tied": len(top), "metrics": top[0].metrics} if top and game.ranked() else None),
            "mine": result_view(mine, nick[viewer.id], my_place, True, True) if mine else None,
        })
    items.sort(key=lambda i: (i["filed"], i["resets_at"]))
    return {"now": now.isoformat(), "items": items}


def minutes(s: Session, board: Board, viewer: Person, game_id: str, day: date | None,
            now: datetime | None = None) -> dict[str, Any]:
    now = now or utcnow()
    game = REGISTRY[game_id]
    current_day = game_day(game_id, viewer, now)
    day = day or current_day
    players = _players(s, board, game_id)
    nick = {m.person_id: m.nickname for m in players}
    rows = _results(s, game_id, day, list(nick))
    placed = _placed(rows)
    mine = next((r for r in rows if r.person_id == viewer.id), None)
    # filed anywhere counts: you've seen the puzzle even if it's not on your agenda here
    seen = mine or s.scalar(select(Result).where(
        Result.person_id == viewer.id, Result.game_id == game_id, Result.puzzle_day == day,
        Result.withdrawn_at.is_(None)))
    filed_ids = {r.person_id for r in rows}
    return {
        "game": game_id, "name": game.name, "ranked": game.ranked(), "day": day.isoformat(),
        "current": day == current_day,
        "resets_at": next_reset(game_id, viewer, now).isoformat() if day == current_day else None,
        "open": seen is not None,
        "rows": [result_view(r, nick[r.person_id], _place_label(placed, p), seen is not None,
                             r.person_id == viewer.id) for p, r in placed],
        "not_in": sorted(nick[m.person_id] for m in players if m.person_id not in filed_ids),
    }
