"""A member's activity on one board: =member(board, who).

What they play here, how each game is going (tenure, wins, average, best), their last
results with the place each took, and the latest memos about them. As everywhere on a
board, only games on their agenda here and in the board's library count, and a result
shows its score but none of its details (the route, the grid): those stay in the minutes,
behind filing the puzzle yourself."""
from __future__ import annotations

import statistics
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import memos
from .errors import fail
from .filing import to_parsed
from .models import Agenda, Board, Person, Result, utcnow
from .parser import REGISTRY
from .parser.rank import rank
from .reads import _key, _place_label, _placed, _players, game_day, tenure

WINDOW = 30  # puzzles back that wins, averages and the strip look at
RECENT = 20  # results in the activity list
MEMOS = 6    # memos about them


def member(s: Session, board: Board, viewer: Person, nickname: str, now: datetime | None = None) -> dict[str, Any]:
    now = now or utcnow()
    m = next((x for x in board.memberships if x.nickname == nickname and x.left_at is None), None)
    if m is None:
        fail(404, f"no one called {nickname} on this board")
    pid = m.person_id
    lib = {bg.game_id for bg in board.library}
    games = sorted((g for g in s.scalars(select(Agenda.game_id).where(Agenda.board_id == board.id, Agenda.person_id == pid))
                    if g in lib and g in REGISTRY), key=lambda g: REGISTRY[g].name)
    local = now.astimezone(ZoneInfo(viewer.tz)).date()
    strip = [0] * WINDOW  # results filed on each of the last 30 days (daily games), today last
    per_game, recent = [], []
    for g in games:
        G = REGISTRY[g]
        every, cur = G.reset.every, game_day(g, viewer, now)
        mine = list(s.scalars(select(Result).where(
            Result.person_id == pid, Result.game_id == g, Result.withdrawn_at.is_(None),
            Result.puzzle_day.is_not(None), Result.puzzle_day <= cur)))
        run, longest, at_risk = tenure({r.puzzle_day for r in mine}, cur, every)
        since = cur - timedelta(days=WINDOW * every)
        window = [r for r in mine if r.puzzle_day > since]
        # everyone's results on those puzzles, for the place each took
        players = [p.person_id for p in _players(s, board, g)]
        days = {r.puzzle_day for r in window}
        field: dict[date, list[Result]] = {}
        if days:
            for r in s.scalars(select(Result).where(Result.game_id == g, Result.puzzle_day.in_(days),
                                                    Result.person_id.in_(players), Result.withdrawn_at.is_(None))):
                field.setdefault(r.puzzle_day, []).append(r)
        place: dict[int, tuple[str, int]] = {}
        wins = 0
        for d, rows in field.items():
            placed = _placed(rows)
            for p, r in placed:
                if r.person_id == pid:
                    place[r.id] = (_place_label(placed, p), len(rows))
                    wins += G.ranked() and p == 1 and len(rows) > 1
        key = _key(g) if G.ranked() else None
        vals = [r.metrics[key] for r in window if key and key in r.metrics and r.outcome != "failed"]
        best = rank([to_parsed(r) for r in mine])[0][1] if G.ranked() and mine else None
        last = max(mine, key=lambda r: (r.puzzle_day, r.filed_at), default=None)
        per_game.append({
            "game": g, "name": G.name, "ranked": G.ranked(), "weekly": G.weekly(),
            "results": len(mine), "played": len(window), "wins": wins,
            "tenure": run, "longest": longest, "at_risk": at_risk,
            "average": round(statistics.mean(vals), 2) if vals else None,
            "best": dict(best.metrics) if best else None,
            "last": last.puzzle_day.isoformat() if last else None,
            "today": cur.isoformat(),
        })
        for r in window:
            if not G.weekly() and 0 <= (local - r.puzzle_day).days < WINDOW:
                strip[WINDOW - 1 - (local - r.puzzle_day).days] += 1
            p, n = place.get(r.id, ("", 0))
            recent.append({"game": g, "name": G.name, "weekly": G.weekly(), "day": r.puzzle_day.isoformat(),
                           "puzzle": r.puzzle_key, "outcome": r.outcome, "metrics": r.metrics, "highlights": r.highlights,
                           "late": r.late, "place": p, "of": n, "filed_at": r.filed_at.isoformat()})
    recent.sort(key=lambda x: (x["day"], x["filed_at"]), reverse=True)
    daily = [g for g in per_game if not g["weekly"]]
    return {
        "nickname": m.nickname, "me": pid == viewer.id, "role": m.role, "joined_at": m.joined_at.isoformat(),
        "today": local.isoformat(),
        "games": per_game,
        "daily": len(daily),  # the strip's top: every daily game on their agenda
        "strip": strip,
        "present": sum(1 for c in strip[-7:] if c),  # days with anything filed, of the last 7
        "wins": sum(g["wins"] for g in per_game),
        "recent": recent[:RECENT],
        "memos": memos.about(s, board, viewer, pid, MEMOS),
    }
