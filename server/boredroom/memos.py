"""Memos from the chair: board gossip, read off the results (UX-NOTES §5).

A rule is a function from one board's results to candidate memos. The first time a memo
is seen it's stored under a key unique to its board, so its facts stay fixed: a late
filing can add memos but never rewrites one, the way the minutes aren't re-dated. Text is
rendered when it's read, from the kind and the facts, so it can say "you" to the person
it's about and its wording can change without touching the rows.

A memo belongs to the day of the board meeting that reports it. What happens inside a
live puzzle (a record, a personal best, a tenure milestone) is reported on that puzzle's
day; what needs the puzzle closed first (a photo finish, a comeback, #1 changing hands
over the rolling week) is reported the day after it closes.

Only the last two days are ever looked at, so the imported history never arrives as
three hundred memos at once."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Callable, Iterator
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from . import reads
from .errors import fail
from .filing import to_parsed
from .models import Agenda, Board, Memo, MemoDismissal, Person, Result, utcnow
from .parser import REGISTRY
from .parser.rank import compare

WEEK = 7  # the rolling week: the review's, the takeover's and the pip's
AGENDA = 3  # memos on the agenda, at most
EVERY = 60  # seconds between two runs of one board's rules
MILESTONES = (7, 30, 50, 100)  # then every 100
GLYPH = {"takeover": "▲", "pip": "▼", "record": "♛", "pb": "★", "highlight": "✦", "tenure": "◆",
         "ended": "◇", "photo": "≈", "comeback": "↗", "missed": "✗"}
# the agenda only carries the big news; everything is in the meeting
ON_AGENDA = {"takeover", "record", "pb", "highlight", "tenure", "ended"}


@dataclass
class Candidate:
    key: str
    kind: str
    day: date
    subjects: list[int]
    interest: int
    game: str | None = None
    result: int | None = None
    facts: dict[str, Any] = field(default_factory=dict)


class Ledger:
    """One board's results, loaded once for all the rules: every puzzle filed by a member
    who has that game on their agenda here, the way the review counts them."""

    def __init__(self, s: Session, board: Board, viewer: Person, now: datetime):
        self.s, self.board = s, board
        self.nick = {m.person_id: m.nickname for m in board.memberships if m.left_at is None}
        self.players: dict[str, set[int]] = {}
        for a in s.scalars(select(Agenda).where(Agenda.board_id == board.id)):
            if a.person_id in self.nick:
                self.players.setdefault(a.game_id, set()).add(a.person_id)
        lib = {bg.game_id for bg in board.library}
        self.games = sorted(g for g in self.players if g in lib and g in REGISTRY)
        self.current = {g: reads.game_day(g, viewer, now) for g in self.games}
        self.by: dict[tuple[str, date], list[Result]] = {}
        self.history: dict[str, list[Result]] = {g: [] for g in self.games}
        if self.games:
            for r in s.scalars(select(Result).where(
                    Result.game_id.in_(self.games), Result.person_id.in_(list(self.nick)),
                    Result.withdrawn_at.is_(None), Result.puzzle_day.is_not(None))):
                if r.person_id in self.players[r.game_id] and r.puzzle_day <= self.current[r.game_id]:
                    self.by.setdefault((r.game_id, r.puzzle_day), []).append(r)
                    self.history[r.game_id].append(r)
        self._parsed: dict[int, Any] = {}
        self._placed: dict[tuple[str, date], list[tuple[int, Result]]] = {}

    def ranked(self, g: str) -> bool:
        return REGISTRY[g].ranked()

    def p(self, r: Result):
        if r.id not in self._parsed:
            self._parsed[r.id] = to_parsed(r)
        return self._parsed[r.id]

    def better(self, a: Result, b: Result) -> bool:
        return compare(self.p(a), self.p(b)) < 0

    def placed(self, g: str, d: date) -> list[tuple[int, Result]]:
        if (g, d) not in self._placed:
            self._placed[(g, d)] = reads._placed(self.by.get((g, d), []))
        return self._placed[(g, d)]

    def days(self, g: str, pid: int) -> set[date]:
        return {r.puzzle_day for r in self.history[g] if r.person_id == pid}

    def live(self) -> Iterator[tuple[str, date]]:
        """Puzzles that may still be open: each game's current one and the one before."""
        for g in self.games:
            for back in (0, 1):
                yield g, self.current[g] - timedelta(days=back)

    def closed(self) -> Iterator[tuple[str, date]]:
        """The last two puzzles that have closed, for each game."""
        for g in self.games:
            for back in (1, 2):
                yield g, self.current[g] - timedelta(days=back)

    def week(self, until: date) -> tuple[dict[int, int], dict[int, set[date]]]:
        """Daily wins and days present over the rolling week of closed puzzles before `until`."""
        wins: dict[int, int] = {}
        present: dict[int, set[date]] = {}
        for g in self.games:
            for back in range(1, WEEK + 1):
                d = until - timedelta(days=back)
                rs = self.by.get((g, d), [])
                for p, r in (self.placed(g, d) if self.ranked(g) else []):
                    present.setdefault(r.person_id, set()).add(d)
                    if p == 1 and len(rs) > 1:
                        wins[r.person_id] = wins.get(r.person_id, 0) + 1
        return wins, present


RULES: list[Callable[[Ledger], Iterator[Candidate]]] = []


def rule(f: Callable[[Ledger], Iterator[Candidate]]) -> Callable[[Ledger], Iterator[Candidate]]:
    RULES.append(f)
    return f


def _facts(r: Result, d: date) -> dict[str, Any]:
    return {"on": d.isoformat(), "metrics": r.metrics, "outcome": r.outcome}


@rule
def records_and_bests(b: Ledger) -> Iterator[Candidate]:
    """A board record beats every earlier result on the board (10+ of them); a personal
    best beats all of your own (5+). A record is never also announced as a best."""
    for g, d in b.live():
        rs = b.by.get((g, d), [])
        if not rs or not b.ranked(g):
            continue
        before = [r for r in b.history[g] if r.puzzle_day < d]
        holder = None
        if len(before) >= 10:
            top = sorted((r for p, r in b.placed(g, d) if p == 1), key=lambda r: r.filed_at)[0]
            if all(b.better(top, r) for r in before):
                holder = top
                yield Candidate(f"record:{g}:{d}", "record", d, [top.person_id], 85, g, top.id, _facts(top, d))
        for r in rs:
            mine = [x for x in before if x.person_id == r.person_id]
            if r is not holder and len(mine) >= 5 and all(b.better(r, x) for x in mine):
                yield Candidate(f"pb:{g}:{r.person_id}:{d}", "pb", d, [r.person_id], 55, g, r.id, _facts(r, d))


@rule
def highlights(b: Ledger) -> Iterator[Candidate]:
    """What the game itself calls out (flawless, perfect, grade s), and how often lately."""
    for g, d in b.live():
        for r in b.by.get((g, d), []):
            h = next((h for h in r.highlights if h != "personal best"), None)  # bests are ours to call
            if h is None:
                continue
            n = sum(1 for x in b.history[g] if x.person_id == r.person_id and h in x.highlights
                    and d - timedelta(days=WEEK) < x.puzzle_day <= d)
            yield Candidate(f"highlight:{g}:{r.person_id}:{d}", "highlight", d, [r.person_id],
                            65 if n > 1 else 50, g, r.id, {"on": d.isoformat(), "h": h, "n": n})


@rule
def tenures(b: Ledger) -> Iterator[Candidate]:
    """A tenure reaching 7, 30, 50, 100 days and every 100 after; one of 7+ days ending."""
    for g, d in b.live():
        for r in b.by.get((g, d), []):
            run = reads.tenure(b.days(g, r.person_id), d)[0]
            if run in MILESTONES or run > 100 and run % 100 == 0:
                yield Candidate(f"tenure:{g}:{r.person_id}:{d}", "tenure", d, [r.person_id],
                                50 + min(run // 5, 30), g, r.id, {"on": d.isoformat(), "n": run})
    for g, gap in b.closed():
        last = gap - timedelta(days=1)
        for pid in b.players[g]:
            days = b.days(g, pid)
            if gap in days or last not in days:
                continue
            run = reads.tenure({x for x in days if x <= last}, last)[0]
            if run >= 7:
                yield Candidate(f"ended:{g}:{pid}:{last}", "ended", gap + timedelta(days=1), [pid], 60, g,
                                facts={"on": last.isoformat(), "gap": gap.isoformat(), "n": run})


@rule
def closings(b: Ledger) -> Iterator[Candidate]:
    """Once a puzzle closes: a tie for #1, a comeback from last, a tough room."""
    for g, d in b.closed():
        rs = b.by.get((g, d), [])
        report = d + timedelta(days=1)
        if not rs:
            continue
        if b.ranked(g):
            placed = b.placed(g, d)
            first = [r for p, r in placed if p == 1]
            if len(rs) >= 2 and len(first) >= 2 and first[0].outcome != "failed":
                yield Candidate(f"photo:{g}:{d}", "photo", report, sorted(r.person_id for r in first), 45, g,
                                facts=_facts(first[0], d))
            before = b.placed(g, d - timedelta(days=1))
            if len(placed) >= 3 and len(before) >= 3 and len(first) == 1:
                worst = max(p for p, _ in before)
                last = [r for p, r in before if p == worst]
                if len(last) == 1 and last[0].person_id == first[0].person_id and worst > 1:
                    pid = first[0].person_id
                    yield Candidate(f"comeback:{g}:{pid}:{d}", "comeback", report, [pid], 40, g, first[0].id,
                                    {"on": d.isoformat()})
        missed = sum(r.outcome == "failed" for r in rs)
        if missed >= 2:  # never one person singled out
            yield Candidate(f"missed:{g}:{d}", "missed", report, [], 10, g,
                            facts={"on": d.isoformat(), "n": missed, "of": len(rs)})


def _leader(wins: dict[int, int]) -> int | None:
    top = max(wins.values(), default=0)
    who = [p for p, w in wins.items() if w == top]
    return who[0] if top and len(who) == 1 else None


@rule
def the_week(b: Ledger) -> Iterator[Candidate]:
    """The rolling week's daily wins: #1 changing hands, and who's last (a pip). Reported
    once every game's previous puzzle has closed, so the count can't move after."""
    ranked = [g for g in b.games if b.ranked(g)]
    if not ranked:
        return
    today = min(b.current[g] for g in ranked)
    for day in (today - timedelta(days=1), today):
        wins, present = b.week(day)
        now, was = _leader(wins), _leader(b.week(day - timedelta(days=1))[0])
        if now and was and now != was and not _recent(b, "takeover", {now, was}, day, 3):
            yield Candidate(f"takeover:{day}:{now}>{was}", "takeover", day, [now, was], 90,
                            facts={"wins": wins[now], "was": wins.get(was, 0)})
        # a pip: last among 4+ present, of those here 3+ days and filing for at least a week
        first = {p: min((r.puzzle_day for g in b.games for r in b.history[g] if r.person_id == p), default=day)
                 for p in present}
        able = [p for p in present if len(present[p]) >= 3 and first[p] <= day - timedelta(days=WEEK)]
        if len(present) >= 4 and len(able) >= 2:
            low = min(wins.get(p, 0) for p in able)
            last = [p for p in able if wins.get(p, 0) == low]
            if len(last) == 1 and not _recent(b, "pip", {last[0]}, day, WEEK):
                p = last[0]
                yield Candidate(f"pip:{p}:{day}", "pip", day, [p], 70, facts={"wins": low, "days": len(present[p])})


def _recent(b: Ledger, kind: str, who: set[int], day: date, days: int) -> bool:
    """Was this kind of memo about these people posted in the last `days` days?"""
    return any(set(m.subjects) == who for m in b.s.scalars(select(Memo).where(
        Memo.board_id == b.board.id, Memo.kind == kind, Memo.day > day - timedelta(days=days), Memo.day <= day)))


_ran: dict[tuple[int, float], float] = {}


def refresh(s: Session, board: Board, viewer: Person, now: datetime | None = None) -> int:
    """Runs the rules and stores what's new; returns how many. A board's rules run at most
    once a minute, unless `now` is given (tests, mostly)."""
    if now is None:
        k = (board.id, board.created_at.timestamp())
        if time.monotonic() - _ran.get(k, -EVERY) < EVERY:
            return 0
        _ran[k] = time.monotonic()
    now = now or utcnow()
    b = Ledger(s, board, viewer, now)
    new = 0
    for r in RULES:
        for c in r(b):
            new += len(s.execute(insert(Memo).values(
                board_id=board.id, key=c.key, kind=c.kind, day=c.day, subjects=c.subjects, game_id=c.game,
                result_id=c.result, facts=c.facts, interest=c.interest, created_at=now,
            ).on_conflict_do_nothing(index_elements=["board_id", "key"]).returning(Memo.id)).all())
    s.flush()
    return new


# -- reading ------------------------------------------------------------------

def _names(xs: list[str]) -> str:
    return xs[0] if len(xs) == 1 else f"{', '.join(xs[:-1])} and {xs[-1]}"


def text(m: Memo, nick: dict[int, str], me: int | None) -> str:
    """The memo's line, for `me` (None: for the group chat, names only)."""
    def n(p: int) -> str:
        return "you" if p == me else nick.get(p, "a former member")

    def pos(p: int) -> str:
        return "your" if p == me else f"{n(p)}'s"
    game = REGISTRY[m.game_id].name.lower() if m.game_id in REGISTRY else ""
    f, k = m.facts, m.kind
    p = m.subjects[0] if m.subjects else None
    if k == "takeover":
        a, was = m.subjects
        if me == was:
            return f"hostile takeover: {n(a)} passed you for #1 this week."
        return f"{n(a)} took #1 from {n(was)} this week. the board is reorganising."
    if k == "pip":
        if p == me:
            return "you're on a pip. the board believes in you, mostly."
        return f"{n(p)} is on a pip: {f['wins']} daily wins in {f['days']} days present."
    if k == "record":
        return f"board record on {game}: {n(p)}. it will be framed."
    if k == "pb":
        return f"{n(p)} set a personal best on {game}."
    if k == "highlight":
        again = f" that's {f['n']} in a week." if f["n"] > 1 else ""
        return f"{n(p)} on {game}: {f['h']}.{again}"
    if k == "tenure":
        return f"{pos(p)} {f['n']}-day tenure on {game}. the board notes the commitment."
    if k == "ended":
        return f"{pos(p)} {f['n']}-day {game} tenure ended. a moment of silence."
    if k == "photo":
        names = sorted((n(x) for x in m.subjects), key=lambda x: (x == "you", x))
        return f"photo finish on {game}: {_names(names)}. the chair abstains."
    if k == "comeback":
        return f"comeback on {game}: {n(p)}, last the day before, first this time."
    if k == "missed":
        return f"{f['n']} members missed target on {game}. a tough room."
    return k


def _number(m: Memo) -> str:
    f = m.facts
    return {"takeover": lambda: f"{f['wins']}–{f['was']}", "pip": lambda: f"{f['wins']} wins",
            "tenure": lambda: f"{f['n']}d", "ended": lambda: f"{f['n']}d",
            "highlight": lambda: f"×{f['n']}" if f["n"] > 1 else "", "comeback": lambda: "#1",
            "missed": lambda: f"{f['n']}/{f['of']}"}.get(m.kind, lambda: "")()


def _link(m: Memo, slug: str) -> str:
    if m.kind in ("takeover", "pip"):
        return f"/b/{slug}/review?period=week"
    if m.kind == "record":
        return f"/b/{slug}/review?period=all&game={m.game_id}"
    return f"/b/{slug}/m/{m.game_id}/{m.facts['on']}"


def memo_json(m: Memo, board: Board, nick: dict[int, str], me: Person, dismissed: set[int]) -> dict[str, Any]:
    scored = m.kind in ("record", "pb", "photo")
    return {
        "id": m.id, "kind": m.kind, "glyph": GLYPH.get(m.kind, "·"), "day": m.day.isoformat(), "game": m.game_id,
        "text": text(m, nick, me.id), "plain": text(m, nick, None),
        "number": _number(m), "score": {"metrics": m.facts["metrics"], "outcome": m.facts["outcome"]} if scored else None,
        "link": _link(m, board.slug), "about": [nick[p] for p in m.subjects if p in nick],
        "me": me.id in m.subjects, "dismissed": m.id in dismissed,
    }


def _visible(s: Session, board: Board, q) -> tuple[list[Memo], dict[int, str]]:
    """Memos as they stand: one whose result was withdrawn is hidden, and so is a tenure
    that only looked ended until the missing day was filed late."""
    rows = list(s.scalars(q))
    gone = {i for (i,) in s.execute(select(Result.id).where(
        Result.id.in_([m.result_id for m in rows if m.result_id]), Result.withdrawn_at.is_not(None)))}
    out = []
    for m in rows:
        if m.result_id in gone:
            continue
        if m.kind == "ended" and s.scalar(select(Result.id).where(
                Result.person_id == m.subjects[0], Result.game_id == m.game_id,
                Result.puzzle_day == date.fromisoformat(m.facts["gap"]), Result.withdrawn_at.is_(None)).limit(1)):
            continue
        out.append(m)
    nick = {ms.person_id: ms.nickname for ms in board.memberships}
    return out, nick


def _dismissed(s: Session, viewer: Person, ids: list[int]) -> set[int]:
    return set(s.scalars(select(MemoDismissal.memo_id).where(
        MemoDismissal.person_id == viewer.id, MemoDismissal.memo_id.in_(ids)))) if ids else set()


def local_day(viewer: Person, now: datetime) -> date:
    return now.astimezone(ZoneInfo(viewer.tz)).date()


def agenda(s: Session, board: Board, viewer: Person, now: datetime | None = None) -> list[dict[str, Any]]:
    """The agenda's few: the big news of the last day and a half that you haven't waved
    off. Yours first, newer first (a record beaten the next day gives way to the new
    one); one per kind and one per person, so a single name
    never fills the box."""
    now = now or utcnow()
    since = local_day(viewer, now) - timedelta(days=1)
    rows, nick = _visible(s, board, select(Memo).where(
        Memo.board_id == board.id, Memo.day >= since, Memo.kind.in_(ON_AGENDA)))
    dismissed = _dismissed(s, viewer, [m.id for m in rows])

    def score(m: Memo) -> float:
        age = (now - m.created_at).total_seconds() / 3600
        return m.interest + 20 * (viewer.id in m.subjects) - 10 * (age // 12)
    picked, kinds, people = [], set(), set()
    for m in sorted((m for m in rows if m.id not in dismissed), key=lambda m: (-score(m), -m.day.toordinal(), -m.id)):
        if m.kind in kinds or people & set(m.subjects):
            continue
        picked.append(m)
        kinds.add(m.kind)
        people |= set(m.subjects)
        if len(picked) == AGENDA:
            break
    return [memo_json(m, board, nick, viewer, dismissed) for m in picked]


def meeting(s: Session, board: Board, viewer: Person, day: date | None, now: datetime | None = None) -> dict[str, Any]:
    """The daily bored meeting: every memo reported on one day, the biggest news first."""
    now = now or utcnow()
    today = local_day(viewer, now)
    day = day or today
    rows, nick = _visible(s, board, select(Memo).where(Memo.board_id == board.id, Memo.day == day))
    rows.sort(key=lambda m: (-m.interest, m.id))
    dismissed = _dismissed(s, viewer, [m.id for m in rows])
    earlier = s.scalar(select(Memo.day).where(Memo.board_id == board.id, Memo.day < day)
                       .order_by(Memo.day.desc()).limit(1))
    return {"day": day.isoformat(), "today": today.isoformat(), "earlier": earlier.isoformat() if earlier else None,
            "memos": [memo_json(m, board, nick, viewer, dismissed) for m in rows]}


def dismiss(s: Session, board: Board, viewer: Person, memo_id: int, on: bool) -> None:
    m = s.get(Memo, memo_id)
    if m is None or m.board_id != board.id:
        fail(404, "no such memo")
    row = s.get(MemoDismissal, (viewer.id, memo_id))
    if on and row is None:
        s.add(MemoDismissal(person_id=viewer.id, memo_id=memo_id))
    elif not on and row is not None:
        s.delete(row)
    s.flush()
