"""Board reads: today's agenda and one puzzle's minutes (docs/SERVER.md part 4).

Everything is computed per request. Visibility is enforced here: detail and spoiler
fields, the raw paste and extras only reach someone who has filed that puzzle."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .filing import to_parsed
from .models import Agenda, Board, Membership, Person, Result, Skip, utcnow
from .parser import REGISTRY
from .parser.forward import forward_text
from .parser.rank import compare, rank
from .errors import fail


def game_day(game_id: str, viewer: Person, now: datetime) -> date:
    return REGISTRY[game_id].reset.game_day(now, viewer.tz)


def next_reset(game_id: str, viewer: Person, now: datetime) -> datetime:
    """When the current puzzle closes: the reset after its game day (a week on, for a weekly game)."""
    reset = REGISTRY[game_id].reset
    tz = ZoneInfo(reset.tz or viewer.tz)
    nxt = game_day(game_id, viewer, now) + timedelta(days=reset.every)
    return datetime.combine(nxt, reset.at, tz)


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


def tenure(days: set[date], today: date, every: int = 1) -> tuple[int, int, bool]:
    """A streak, in the board's words: (current, longest, at risk). Current counts back
    from `today` if it's filed, else from yesterday, when it's still alive but at risk.
    A weekly game's puzzles are `every=7` days apart, so its streak counts weeks."""
    longest = run = 0
    prev = None
    for d in sorted(days):
        run = run + 1 if prev is not None and (d - prev).days == every else 1
        longest, prev = max(longest, run), d
    end = today if today in days else today - timedelta(days=every)
    current = 0
    while end - timedelta(days=current * every) in days:
        current += 1
    return current, longest, current > 0 and today not in days


def _days(s: Session, game_id: str, people: list[int], until: date) -> dict[int, set[date]]:
    """Each person's filed days for a game, up to `until`."""
    out: dict[int, set[date]] = {p: set() for p in people}
    if people:
        for p, d in s.execute(select(Result.person_id, Result.puzzle_day).where(
                Result.game_id == game_id, Result.person_id.in_(people), Result.puzzle_day <= until,
                Result.withdrawn_at.is_(None), Result.puzzle_day.is_not(None))):
            out[p].add(d)
    return out


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
    skips = set(s.execute(select(Skip.game_id, Skip.day).where(Skip.person_id == viewer.id)).all())
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
        run, _, risk = tenure(_days(s, g, [viewer.id], day)[viewer.id], day, game.reset.every)
        items.append({
            "tenure": {"days": run, "at_risk": risk},
            "game": g, "name": game.name, "ranked": game.ranked(), "weekly": game.weekly(), "links": list(game.links),
            "play": game.play_url(),
            "day": day.isoformat(),
            "puzzle": mine.puzzle_key if mine else (str(current.isoformat() if isinstance(current, date)
                                                       else current) if current is not None else None),
            "resets_at": next_reset(g, viewer, now).isoformat(),
            "filed": mine is not None,
            "skipped": (g, day) in skips and mine is None,  # sitting it out till reset; filing wins
            "place": my_place,
            "present": len(rows), "players": len(players),
            "filed_by": sorted(nick[r.person_id] for r in rows),
            "leader": ({"nickname": nick[top[0].person_id] if len(top) == 1 else None,
                        "tied": len(top), "metrics": top[0].metrics} if top and game.ranked() else None),
            "mine": result_view(mine, nick[viewer.id], my_place, True, True) if mine else None,
        })
    # open first; within each, the games you've filed most often, then the soonest reset
    filed = dict(s.execute(select(Result.game_id, func.count()).where(
        Result.person_id == viewer.id, Result.withdrawn_at.is_(None)).group_by(Result.game_id)).all())
    # how much the board plays each one: results by its members over the last 30 days
    members = [m.person_id for m in board.memberships if m.left_at is None]
    since = (now - timedelta(days=30)).date()
    month = dict(s.execute(select(Result.game_id, func.count()).where(
        Result.game_id.in_(games), Result.person_id.in_(members), Result.puzzle_day >= since,
        Result.withdrawn_at.is_(None)).group_by(Result.game_id)).all()) if games and members else {}
    for i in items:
        i["results"] = filed.get(i["game"], 0)
        i["board_month"] = month.get(i["game"], 0)
    items.sort(key=lambda i: (i["filed"], -i["results"], i["resets_at"]))
    return {"now": now.isoformat(), "items": items}


def skip(s: Session, viewer: Person, game_id: str, on: bool, now: datetime | None = None) -> None:
    """Sits a game out until it resets, or brings it back. Today's puzzle only: the skip
    is kept against the game day, so tomorrow's agenda has the game again."""
    if game_id not in REGISTRY:
        fail(404, "no such game")
    day = game_day(game_id, viewer, now or utcnow())
    row = s.get(Skip, (viewer.id, game_id, day))
    if on and row is None:
        s.add(Skip(person_id=viewer.id, game_id=game_id, day=day))
    elif not on and row is not None:
        s.delete(row)
    # yesterday's skips have run out; nothing reads them
    s.execute(Skip.__table__.delete().where(Skip.person_id == viewer.id, Skip.day < day - timedelta(days=2)))


def minutes(s: Session, board: Board, viewer: Person, game_id: str, day: date | None,
            now: datetime | None = None) -> dict[str, Any]:
    now = now or utcnow()
    game = REGISTRY[game_id]
    current_day = game_day(game_id, viewer, now)
    day = game.week_of(day) if day else current_day
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
    runs = {p: tenure(ds, day, game.reset.every)[0] for p, ds in _days(s, game_id, list(filed_ids), day).items()}
    return {
        "game": game_id, "name": game.name, "ranked": game.ranked(), "weekly": game.weekly(), "day": day.isoformat(),
        "current": day == current_day,
        "resets_at": next_reset(game_id, viewer, now).isoformat() if day == current_day else None,
        "open": seen is not None,
        "rows": [result_view(r, nick[r.person_id], _place_label(placed, p), seen is not None,
                             r.person_id == viewer.id) | {"tenure": runs.get(r.person_id, 0)} for p, r in placed],
        "not_in": sorted(nick[m.person_id] for m in players if m.person_id not in filed_ids),
    }


PERIODS = {"today": 1, "week": 7, "month": 30, "all": None}  # game days, counting back from today's
STRIP = 30  # days in the "last 30" strip
# what the standings can be sorted by: across all games, or within one
STATS = {None: ("wins", "rate", "days", "filed"), "game": ("average", "best", "wins", "played", "tenure", "longest")}
MIN_PLAYS = {"today": 1, "week": 3, "month": 5, "all": 10}  # to qualify for a ranking by average
MIN_WEEKS = {"today": 1, "week": 1, "month": 2, "all": 4}  # the same, for a weekly game


def _key(game_id: str) -> str | None:
    """The metric a game's average is taken over: the first in its ranking order."""
    g = REGISTRY[game_id]
    return g.ranker[0] if g.ranker else None


def review(s: Session, board: Board, viewer: Person, period: str = "today", game: str | None = None,
           stat: str | None = None, vs: str | None = None, now: datetime | None = None) -> dict[str, Any]:
    """The board's review (UX-NOTES §2 and §4): one query, written in the formula bar as
    =review(board, period, game, stat, vs). Across all games the standings are daily wins
    (a #1 place, ties included, in a puzzle at least two people filed), win rate, days
    present or puzzles filed; for one game, average, best, wins or plays. `vs` adds a
    head-to-head over the puzzles you both filed, and the 30-day strip follows it."""
    if period not in PERIODS:
        fail(400, f"period is one of {', '.join(PERIODS)}")
    lib = {bg.game_id for bg in board.library}
    if game is not None and (game not in lib or not REGISTRY[game].ranked()):
        fail(400, f"{game} isn't a ranked game on this board")
    stats = STATS["game" if game else None]
    stat = stat or stats[0]
    if stat not in stats:
        fail(400, f"stat is one of {', '.join(stats)}")
    now, span = now or utcnow(), PERIODS[period]
    members = [m for m in board.memberships if m.left_at is None]
    nick = {m.person_id: m.nickname for m in members}
    rival = next((m.person_id for m in members if m.nickname == vs and m.person_id != viewer.id), None) if vs else None
    if vs and rival is None:
        fail(400, f"no one called {vs} on this board")
    agendas: dict[str, set[int]] = {}
    for a in s.scalars(select(Agenda).where(Agenda.board_id == board.id)):
        if a.person_id in nick:
            agendas.setdefault(a.game_id, set()).add(a.person_id)
    # a weekly game has no "today": across games it sits today out, and on its own, "today"
    # is this week's puzzle (a span of one day from its game day, the monday it began)
    games = [game] if game else sorted((g for g in lib if not (period == "today" and REGISTRY[g].weekly())),
                                       key=lambda g: REGISTRY[g].name)
    weekly = bool(game and REGISTRY[game].weekly())
    current = {g: game_day(g, viewer, now) for g in games}
    local = now.astimezone(ZoneInfo(viewer.tz)).date()
    back = max(span or 0, STRIP * (7 if weekly else 1))  # alone, a weekly game's strip is 30 weeks
    rows: dict[tuple[str, date], list[Result]] = {}  # the period and the strip's 30 days
    for g in games:
        q = select(Result).where(Result.game_id == g, Result.person_id.in_(agendas.get(g, set())),
                                 Result.withdrawn_at.is_(None), Result.puzzle_day <= current[g])
        if span:
            q = q.where(Result.puzzle_day > current[g] - timedelta(days=back))
        for r in s.scalars(q):
            rows.setdefault((g, r.puzzle_day), []).append(r)
    in_period = (lambda g, d: d > current[g] - timedelta(days=span)) if span else (lambda g, d: True)
    def ago(g: str, d: date) -> int:  # the strip's cell: days back, or weeks for a weekly game alone
        if weekly:
            return (current[g] - d).days // 7
        return (local - d).days if REGISTRY[g].weekly() else (current[g] - d).days

    who: dict[int, dict[str, Any]] = {}
    def me_(p: int) -> dict[str, Any]:  # noqa: E306
        return who.setdefault(p, {"wins": 0, "days": set(), "filed": 0, "ranked": 0, "vals": [], "best": None})
    best: dict[str, tuple[Result, date]] = {}
    h2h = {"you": 0, "them": 0, "level": 0}
    strip: dict[int, list[int]] = {}  # days ago -> [you ahead, them ahead] (or [won, played])
    for (g, day), rs in rows.items():
        g_ranked = REGISTRY[g].ranked()
        placed = _placed(rs) if g_ranked else [(0, r) for r in rs]
        place_of = {r.person_id: p for p, r in placed}
        mine = next((r for r in rs if r.person_id == viewer.id), None)
        theirs = next((r for r in rs if r.person_id == rival), None) if rival else None
        if ago(g, day) < STRIP:
            cell = strip.setdefault(ago(g, day), [0, 0, 0])
            if rival:
                if mine and theirs and g_ranked:
                    c = compare(to_parsed(mine), to_parsed(theirs))
                    cell[0 if c < 0 else 1 if c > 0 else 2] += 1
            elif mine and g_ranked:
                cell[0 if place_of[viewer.id] == 1 and len(rs) > 1 else 1] += 1
        if not in_period(g, day):
            continue
        for p, r in placed:
            x = me_(r.person_id)
            x["days"].add(day)
            x["filed"] += 1
            if not g_ranked:
                continue
            x["ranked"] += 1
            if p == 1 and len(rs) > 1:
                x["wins"] += 1
            if game and (v := r.metrics.get(_key(g))) is not None:
                x["vals"].append(v)
            if game and (x["best"] is None or compare(to_parsed(r), to_parsed(x["best"][0])) < 0):
                x["best"] = (r, day)
        if rival and mine and theirs and g_ranked:
            c = compare(to_parsed(mine), to_parsed(theirs))
            h2h["you" if c < 0 else "them" if c > 0 else "level"] += 1
        if g_ranked:
            top = placed[0][1]
            if g not in best or compare(to_parsed(top), to_parsed(best[g][0])) < 0 \
                    or compare(to_parsed(top), to_parsed(best[g][0])) == 0 and day < best[g][1]:
                best[g] = (top, day)  # the first to set it keeps a tied record

    high = game and REGISTRY[game].metric_def(_key(game)).better == "high"
    least = (MIN_WEEKS if weekly else MIN_PLAYS)[period]
    alltime = _days(s, game, list(nick), current[game]) if game else {}
    standings = []
    for p in nick:
        if p not in who and p != viewer.id and not (stat in ("tenure", "longest") and alltime.get(p)):
            continue
        x = who.get(p) or me_(p)
        avg = sum(x["vals"]) / len(x["vals"]) if x["vals"] else None
        row = {"nickname": nick[p], "me": p == viewer.id, "wins": x["wins"], "days": len(x["days"]),
               "filed": x["filed"], "rate": round(x["wins"] / x["ranked"], 3) if x["ranked"] else 0.0}
        if game:
            row |= {"played": x["ranked"], "average": round(avg, 2) if avg is not None else None,
                    "best": x["best"][0].metrics if x["best"] else None,
                    "qualified": x["ranked"] >= least and avg is not None}
        row["_best"] = x["best"][0] if game and x["best"] else None
        if game:  # tenure runs over all time, whatever the period
            row["tenure"], row["longest"], row["at_risk"] = tenure(alltime.get(p, set()), current[game], REGISTRY[game].reset.every)
        standings.append(row)

    def order(r: dict[str, Any]) -> tuple:
        if stat == "average":
            a = r["average"]
            return (not r["qualified"], a is None, -(a or 0) if high else (a or 0), r["nickname"])
        if stat == "best":
            return (r["_best"] is None, r["nickname"])  # refined by compare below
        return (-r[stat], -r["days"], r["nickname"])
    standings.sort(key=order)
    if stat == "best":
        from functools import cmp_to_key
        have = [r for r in standings if r["_best"]]
        have.sort(key=cmp_to_key(lambda a, b: compare(to_parsed(a["_best"]), to_parsed(b["_best"])) or (a["nickname"] > b["nickname"]) - (a["nickname"] < b["nickname"])))
        standings = have + [r for r in standings if not r["_best"]]
    value = (lambda r: r["average"] if r["qualified"] else None) if stat == "average" else \
        (lambda r: to_parsed(r["_best"]) if r["_best"] else None) if stat == "best" else (lambda r: r[stat])
    place = 0
    for i, r in enumerate(standings):
        v, prev = value(r), value(standings[i - 1]) if i else None
        same = i and v is not None and prev is not None and (compare(v, prev) == 0 if stat == "best" else v == prev)
        if not same:
            place = i + 1
        r["place"] = place if v not in (None, 0) else None
    for r in standings:
        del r["_best"]

    out: dict[str, Any] = {"period": period, "game": game, "weekly": weekly, "stat": stat, "stats": list(stats), "vs": vs,
                           "now": now.isoformat(), "standings": standings,
                           "members": sorted(n for p, n in nick.items() if p != viewer.id),
                           "ranked_games": sorted((g for g in lib if REGISTRY[g].ranked()), key=lambda g: REGISTRY[g].name)}
    # the strip, oldest first: "on" you won it, "ls" you lost it, "lv" level, "" no contest
    cells = []
    for d in range(STRIP - 1, -1, -1):
        a, b, lv = strip.get(d, [0, 0, 0])
        cells.append("" if not (a or b or lv) else "on" if a > b else "ls" if b > a else "lv")
    out["strip"] = cells
    if rival:
        out["h2h"] = h2h
    if game:
        out["min_plays"], out["metric"] = least, _key(game)
        rec = best.get(game)
        out["record"] = {"nickname": nick[rec[0].person_id], "me": rec[0].person_id == viewer.id,
                         "metrics": rec[0].metrics, "day": rec[1].isoformat()} if rec else None
    elif period == "today":
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
