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
from .parser.forward import forward_text
from .parser.rank import compare, rank
from .errors import fail


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
        "forward": forward_text(to_parsed(row)) if me else None,  # what "send to whatsapp" sends
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


PERIODS = {"today": 1, "week": 7, "month": 30, "all": None}  # game days, counting back from today's


def review(s: Session, board: Board, viewer: Person, period: str = "today",
           now: datetime | None = None) -> dict[str, Any]:
    """The board's review (UX-NOTES §4): daily wins over the period, then today's game by
    game, or each game's best for a longer one. A daily win is a #1 place, ties included,
    in a puzzle at least two people filed."""
    if period not in PERIODS:
        fail(400, f"period is one of {', '.join(PERIODS)}")
    now, span = now or utcnow(), PERIODS[period]
    members = [m for m in board.memberships if m.left_at is None]
    nick = {m.person_id: m.nickname for m in members}
    agendas: dict[str, set[int]] = {}
    for a in s.scalars(select(Agenda).where(Agenda.board_id == board.id)):
        if a.person_id in nick:
            agendas.setdefault(a.game_id, set()).add(a.person_id)
    games = sorted((bg.game_id for bg in board.library), key=lambda g: REGISTRY[g].name)
    current = {g: game_day(g, viewer, now) for g in games}
    first = {g: current[g] - timedelta(days=span - 1) for g in games} if span else {}

    rows: dict[tuple[str, date], list[Result]] = {}
    for g in games:
        q = select(Result).where(Result.game_id == g, Result.person_id.in_(agendas.get(g, set())),
                                 Result.withdrawn_at.is_(None), Result.puzzle_day <= current[g])
        if span:
            q = q.where(Result.puzzle_day >= first[g])
        for r in s.scalars(q):
            rows.setdefault((g, r.puzzle_day), []).append(r)

    wins: dict[int, int] = {}
    days: dict[int, set[date]] = {}
    best: dict[str, tuple[Result, date]] = {}
    for (g, day), rs in rows.items():
        for r in rs:
            days.setdefault(r.person_id, set()).add(day)
        if not REGISTRY[g].ranked():
            continue
        placed = _placed(rs)
        if len(rs) > 1:
            for p, r in placed:
                if p == 1:
                    wins[r.person_id] = wins.get(r.person_id, 0) + 1
        top = placed[0][1]
        if g not in best or compare(to_parsed(top), to_parsed(best[g][0])) < 0 \
                or compare(to_parsed(top), to_parsed(best[g][0])) == 0 and day < best[g][1]:
            best[g] = (top, day)  # the first to set it keeps a tied record

    standings = sorted(({"nickname": nick[p], "me": p == viewer.id, "wins": wins.get(p, 0),
                         "days": len(days.get(p, ()))} for p in nick if p in days or p == viewer.id),
                       key=lambda x: (-x["wins"], -x["days"], x["nickname"]))
    place = 0
    for i, x in enumerate(standings):
        if not i or x["wins"] != standings[i - 1]["wins"]:
            place = i + 1
        x["place"] = place
    out: dict[str, Any] = {"period": period, "now": now.isoformat(), "standings": standings}
    if period == "today":
        out["games"] = []
        for g in games:
            rs = rows.get((g, current[g]), [])
            placed = _placed(rs)
            top = [r for p, r in placed if p == 1]
            mine = next(((p, r) for p, r in placed if r.person_id == viewer.id), None)
            out["games"].append({
                "game": g, "name": REGISTRY[g].name, "ranked": REGISTRY[g].ranked(), "day": current[g].isoformat(),
                "present": len(rs), "players": len(agendas.get(g, ())),
                "plays": viewer.id in agendas.get(g, ()),
                "place": _place_label(placed, mine[0]) if mine else None, "filed": mine is not None,
                "leader": ({"nickname": nick[top[0].person_id] if len(top) == 1 else None, "tied": len(top),
                            "metrics": top[0].metrics} if top and REGISTRY[g].ranked() else None),
            })
    else:
        out["records"] = [{"game": g, "name": REGISTRY[g].name, "nickname": nick[r.person_id], "me": r.person_id == viewer.id,
                           "metrics": r.metrics, "day": d.isoformat()}
                          for g in games if g in best for r, d in [best[g]]]
    return out
