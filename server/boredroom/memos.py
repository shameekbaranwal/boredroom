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

import re
import statistics
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Callable, Iterator
from urllib.parse import quote
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
AGENDA = 2  # memos on the agenda, at most
EVERY = 60  # seconds between two runs of one board's rules
MILESTONES = (7, 30, 50, 100)  # then every 100
ATTENDANCE = (5, 10, 20, 30, 50, 100)  # days of perfect attendance worth a memo, then every 100
RUNS = (4, 7, 10, 14, 21, 30)  # daily wins in a row worth a memo, then every 10
BOARD_COUNTS = (500, 1000, 2500, 5000, 10000)  # the board's nth result, then every 5000
FIXTURES = (4, 8, 13, 26, 52)  # weeks in a row on a weekly game worth a memo, then every 52
REGROUPED = date(2026, 10, 31)  # from here on, highlights are one memo per game and highlight
LOW, LOW_A_DAY = 35, 3  # memos this interesting or less: at most three a day, so the small talk can't crowd the meeting
GLYPH = {"takeover": "▲", "pip": "▼", "record": "♛", "pb": "★", "highlight": "✦", "tenure": "◆",
         "ended": "◇", "photo": "≈", "comeback": "↗", "missed": "✗", "precedent": "§", "run": "⇈",
         "coup": "↯", "jinx": "∥", "unanimous": "⊜", "sweep": "◉", "rumour": "◌", "buzzer": "◷",
         "night": "☾", "milestone": "№", "quorum": "⊞", "usual": "↻", "commendation": "✪", "rivalry": "⇄",
         "earnings": "∆", "attendance": "▣", "champion": "♜", "fixture": "▦", "lastcall": "◔"}
# the agenda only carries the big news; everything is in the meeting
ON_AGENDA = {"takeover", "record", "pb", "highlight", "tenure", "ended", "precedent", "run", "coup", "sweep",
             "rumour", "milestone", "commendation", "attendance", "champion", "fixture", "lastcall"}


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
        self.s, self.board, self.now, self.viewer = s, board, now, viewer
        self.nick = {m.person_id: m.nickname for m in board.memberships if m.left_at is None}
        self.tz = {m.person_id: m.person.tz for m in board.memberships if m.left_at is None}
        self.players: dict[str, set[int]] = {}
        for a in s.scalars(select(Agenda).where(Agenda.board_id == board.id)):
            if a.person_id in self.nick:
                self.players.setdefault(a.game_id, set()).add(a.person_id)
        lib = {bg.game_id for bg in board.library}
        played = sorted(g for g in self.players if g in lib and g in REGISTRY)
        # the daily rules see daily games; weekly games have rules of their own (see `the_weeklies`)
        self.games = [g for g in played if not REGISTRY[g].weekly()]
        self.weeklies = [g for g in played if REGISTRY[g].weekly()]
        self.current = {g: reads.game_day(g, viewer, now) for g in played}
        self.by: dict[tuple[str, date], list[Result]] = {}
        self.history: dict[str, list[Result]] = {g: [] for g in played}
        if played:
            for r in s.scalars(select(Result).where(
                    Result.game_id.in_(played), Result.person_id.in_(list(self.nick)),
                    Result.withdrawn_at.is_(None), Result.puzzle_day.is_not(None))):
                if r.person_id in self.players[r.game_id] and r.puzzle_day <= self.current[r.game_id]:
                    self.by.setdefault((r.game_id, r.puzzle_day), []).append(r)
                    self.history[r.game_id].append(r)
        self._parsed: dict[int, Any] = {}
        self._placed: dict[tuple[str, date], list[tuple[int, Result]]] = {}
        self._days: dict[tuple[str, int], set[date]] = {}

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
        if (g, pid) not in self._days:
            self._days[(g, pid)] = {r.puzzle_day for r in self.history[g] if r.person_id == pid}
        return self._days[(g, pid)]

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

    def day_closed(self) -> date | None:
        """The day before every ranked game's current puzzle: from here back, nothing moves."""
        ranked = [g for g in self.games if self.ranked(g)]
        return min(self.current[g] for g in ranked) if ranked else None

    def wins_run(self, g: str, pid: int, d: date) -> int:
        """Outright daily wins in a row on `g` ending at `d`, each against two or more others."""
        k = 0
        while True:
            day = d - timedelta(days=k)
            first = [r.person_id for p, r in self.placed(g, day) if p == 1]
            if first != [pid] or len(self.by.get((g, day), [])) < 3:
                return k
            k += 1

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
                f = _facts(top, d)
                best = before[0]
                for r in before[1:]:
                    if b.better(r, best) or not b.better(best, r) and r.puzzle_day < best.puzzle_day:
                        best = r
                if best.person_id != top.person_id:
                    f |= {"was": best.person_id, "held": (d - best.puzzle_day).days}
                yield Candidate(f"record:{g}:{d}", "record", d, [top.person_id], 85, g, top.id, f)
        for r in rs:
            mine = [x for x in before if x.person_id == r.person_id]
            if r is not holder and len(mine) >= 5 and all(b.better(r, x) for x in mine):
                yield Candidate(f"pb:{g}:{r.person_id}:{d}", "pb", d, [r.person_id], 55, g, r.id, _facts(r, d))


@rule
def highlights(b: Ledger) -> Iterator[Candidate]:
    """What the game itself calls out (flawless, under par, grade s). The first of its kind
    on the board, with twenty results before it, is a precedent, said at once. The rest wait
    for the puzzle to close, then make one memo per game and highlight naming everyone who
    got it, leaving out whoever already had it in the week before: news, not a roll call."""
    for g, d in b.live():
        for r in b.by.get((g, d), []):
            h = next((h for h in r.highlights if h != "personal best"), None)  # bests are ours to call
            if h is None:
                continue
            earlier = [x for x in b.history[g] if (x.filed_at, x.id) < (r.filed_at, r.id)]
            if len(earlier) >= 20 and not any(h in x.highlights for x in earlier):
                yield Candidate(f"precedent:{g}:{h}", "precedent", d, [r.person_id], 75, g, r.id,
                                {"on": d.isoformat(), "h": h})
    for g, d in b.closed():
        got: dict[str, list[Result]] = {}
        for r in b.by.get((g, d), []):
            h = next((h for h in r.highlights if h != "personal best"), None)  # a result's headline one
            if h is not None:
                got.setdefault(h, []).append(r)
        for h, rs in got.items():
            news = [r for r in rs if not any(
                h in x.highlights and d - timedelta(days=WEEK) <= x.puzzle_day < d
                for x in b.history[g] if x.person_id == r.person_id)]
            if not news:
                continue
            yield Candidate(f"highlight:{g}:{h}:{d}", "highlight", d + timedelta(days=1),
                            sorted(r.person_id for r in news), 50 + 5 * min(len(news) - 1, 2), g,
                            news[0].id if len(news) == 1 else None, {"on": d.isoformat(), "h": h, "k": len(news)})


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
            clean = first[0].outcome != "failed"
            if len(rs) >= 4 and len(first) == len(rs) and clean:
                yield Candidate(f"unanimous:{g}:{d}", "unanimous", report, sorted(r.person_id for r in rs), 45, g,
                                facts=_facts(first[0], d) | {"n": len(rs)})
            elif len(rs) >= 2 and len(first) >= 2 and clean:
                yield Candidate(f"photo:{g}:{d}", "photo", report, sorted(r.person_id for r in first), 45, g,
                                facts=_facts(first[0], d))
            if len(rs) >= 3 and clean:
                for r in first[:1]:
                    k = b.wins_run(g, r.person_id, d)
                    if k in RUNS or k > 30 and k % 10 == 0:
                        yield Candidate(f"run:{g}:{r.person_id}:{d}", "run", report, [r.person_id],
                                        45 if k < 7 else 60 if k < 10 else 70, g, r.id, {"on": d.isoformat(), "n": k})
                if len(first) == 1:
                    w = first[0].person_id
                    fallen = [(b.wins_run(g, r.person_id, d - timedelta(days=1)), r.person_id) for p, r in placed if p > 1]
                    k, h = max(fallen, default=(0, None))
                    if k >= 4:
                        yield Candidate(f"coup:{g}:{d}", "coup", report, [w, h], 65, g, first[0].id,
                                        {"on": d.isoformat(), "n": k})
            before = b.placed(g, d - timedelta(days=1))
            if len(placed) >= 3 and len(before) >= 3 and len(first) == 1:
                worst = max(p for p, _ in before)
                last = [r for p, r in before if p == worst]
                if len(last) == 1 and last[0].person_id == first[0].person_id and worst > 1:
                    pid = first[0].person_id
                    yield Candidate(f"comeback:{g}:{pid}:{d}", "comeback", report, [pid], 40, g, first[0].id,
                                    {"on": d.isoformat()})
        yield from _jinxes(b, g, d, rs, report)
        yield from _buzzers(b, g, d, rs, report)
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
        took = now and was and now != was and not _recent(b, "takeover", {now, was}, day, 3)
        if took:
            yield Candidate(f"takeover:{day}:{now}>{was}", "takeover", day, [now, was], 90,
                            facts={"wins": wins[now], "was": wins.get(was, 0)})
        # a rumour: one daily win off #1, while it's news
        second = _leader({p: w for p, w in wins.items() if p != now}) if now else None
        if (second and wins[second] >= 2 and wins[second] == wins[now] - 1 and not took
                and not _recent(b, "rumour", {second, now}, day, 3) and not _recent(b, "takeover", {second, now}, day, 2)):
            yield Candidate(f"rumour:{day}:{second}>{now}", "rumour", day, [second, now], 50,
                            facts={"wins": wins[second], "lead": wins[now]})
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


def _grid(b: Ledger, r: Result) -> tuple[str, ...] | None:
    """A result's emoji grid, as the game drew it, in one palette (wordle's high-contrast
    and light squares are the same squares)."""
    rows = next((f["value"] for f in r.fields if f["name"] == "grid"), None)
    if not rows or len(rows) < (5 if r.game_id == "connections" else 3):
        return None
    if r.game_id == "wordle":
        rows = [x.replace("⬜", "⬛").replace("🟧", "🟩").replace("🟦", "🟨") for x in rows]
    return tuple(rows)


def _jinxes(b: Ledger, g: str, d: date, rs: list[Result], report: date) -> Iterator[Candidate]:
    """Two or more people with the same grid, square for square. Only on a solve: a shared
    miss is nobody's business."""
    same: dict[tuple[str, ...], list[Result]] = {}
    for r in rs:
        grid = _grid(b, r) if r.outcome != "failed" else None
        if grid:
            same.setdefault(grid, []).append(r)
    for group in same.values():
        if len(group) >= 2:
            who = sorted(r.person_id for r in group)
            yield Candidate(f"jinx:{g}:{d}:{who[0]}", "jinx", report, who, 55 if len(who) > 2 else 45, g,
                            facts=_facts(group[0], d) | {"n": len(who)})


def _buzzers(b: Ledger, g: str, d: date, rs: list[Result], report: date) -> Iterator[Candidate]:
    """Filed in the last ten minutes before the puzzle closed. Once a week each, at most."""
    reset = REGISTRY[g].reset
    for r in rs:
        tz = reset.tz or b.tz.get(r.person_id, "Asia/Kolkata")
        close = datetime.combine(d + timedelta(days=1), reset.at, ZoneInfo(tz))
        left = (close - r.filed_at).total_seconds()
        if r.late or not 0 < left <= 600 or _recent(b, "buzzer", {r.person_id}, report, WEEK):
            continue
        yield Candidate(f"buzzer:{r.person_id}:{d}", "buzzer", report, [r.person_id], 50 if left < 60 else 35, g,
                        r.id, {"on": d.isoformat(), "s": int(left)})


def _closed_days(b: Ledger) -> Iterator[tuple[date, date]]:
    """(the day, the meeting that reports it) for the last two days every game has closed."""
    today = b.day_closed()
    if today:
        for day in (today - timedelta(days=1), today):
            yield day - timedelta(days=1), day


@rule
def sweeps(b: Ledger) -> Iterator[Candidate]:
    """#1 on every ranked item you filed in a day: four or more, each against two others."""
    for d, report in _closed_days(b):
        mine: dict[int, list[int]] = {}
        for g in b.games:
            if b.ranked(g) and len(b.by.get((g, d), [])) >= 3:
                placed = b.placed(g, d)
                tied = sum(p == 1 for p, _ in placed) > 1
                for p, r in placed:
                    mine.setdefault(r.person_id, []).append(0 if p != 1 else 1 if tied else 2)
        for pid, xs in mine.items():
            if len(xs) >= 4 and all(xs) and sum(x == 2 for x in xs) >= 3:
                yield Candidate(f"sweep:{pid}:{d}", "sweep", report, [pid], 80, facts={"on": d.isoformat(), "n": len(xs)})


@rule
def quorum(b: Ledger) -> Iterator[Candidate]:
    """Everyone who's been around lately filed something: five or more. Once a week at most."""
    for d, report in _closed_days(b):
        active, came = set(), set()
        for g in b.games:
            for r in b.history[g]:
                if d - timedelta(days=14) <= r.puzzle_day < d:
                    active.add(r.person_id)
                elif r.puzzle_day == d:
                    came.add(r.person_id)
        if len(active) >= 5 and active <= came and not _recent(b, "quorum", set(), report, WEEK):
            yield Candidate(f"quorum:{d}", "quorum", report, [], 30, facts={"on": d.isoformat(), "n": len(came)})


@rule
def night_shift(b: Ledger) -> Iterator[Candidate]:
    """Filed between 2 and 5 in the morning, your time. Every few days at most."""
    seen: dict[tuple[int, date], list[tuple[datetime, str]]] = {}
    for g, d in b.live():
        for r in b.by.get((g, d), []):
            at = r.filed_at.astimezone(ZoneInfo(b.tz.get(r.person_id, "Asia/Kolkata")))
            if not r.late and 2 <= at.hour < 5:
                seen.setdefault((r.person_id, at.date()), []).append((at, g))
    for (pid, day), xs in sorted(seen.items(), key=lambda x: x[0][1]):
        if _recent(b, "night", {pid}, day, 3):
            continue
        at, g = min(xs)
        yield Candidate(f"night:{pid}:{day}", "night", day, [pid], 20, g if len(xs) == 1 else None,
                        facts={"on": day.isoformat(), "at": at.strftime("%H:%M"), "n": len(xs)})


@rule
def milestones(b: Ledger) -> Iterator[Candidate]:
    """The board's 500th, 1,000th, … result, filed in the last two days (the import's
    history never counts as news)."""
    every = sorted((r for g in b.games for r in b.history[g]), key=lambda r: (r.filed_at, r.id))
    n = BOARD_COUNTS[-1] + 5000
    marks = [*BOARD_COUNTS]
    while n <= len(every):
        marks.append(n)
        n += 5000
    for n in marks:
        if n <= len(every) and every[n - 1].filed_at >= b.now - timedelta(hours=48):
            r = every[n - 1]
            yield Candidate(f"milestone:{n}", "milestone", r.puzzle_day, [r.person_id], 75, r.game_id, r.id,
                            {"on": r.puzzle_day.isoformat(), "n": n})


@rule
def the_usual(b: Ledger) -> Iterator[Candidate]:
    """The same score five (or ten) puzzles running: solved each time, nothing special."""
    for g, d in b.live():
        if not b.ranked(g):
            continue
        for r in b.by.get((g, d), []):
            if r.outcome == "failed" or r.highlights:
                continue
            k = 1
            while True:
                prev = [x for x in b.by.get((g, d - timedelta(days=k)), []) if x.person_id == r.person_id]
                if not prev or prev[0].outcome == "failed" or prev[0].highlights or prev[0].metrics != r.metrics:
                    break
                k += 1
            if k in (5, 10):
                yield Candidate(f"usual:{g}:{r.person_id}:{d}", "usual", d, [r.person_id], 25, g, r.id,
                                _facts(r, d) | {"n": k})


@rule
def member_of_the_month(b: Ledger) -> Iterator[Candidate]:
    """On the 1st: the best daily-win rate over the month just ended, thirty contested
    puzzles or more. A rate, not a count, or it goes to whoever plays the most games."""
    today = b.day_closed()
    for day in ((today - timedelta(days=1), today) if today else ()):
        if day.day != 1:
            continue
        start = (day - timedelta(days=1)).replace(day=1)
        wins: dict[int, int] = {}
        played: dict[int, int] = {}
        for g in b.games:
            if not b.ranked(g):
                continue
            d = start
            while d < day:
                if len(b.by.get((g, d), [])) >= 2:
                    for p, r in b.placed(g, d):
                        played[r.person_id] = played.get(r.person_id, 0) + 1
                        wins[r.person_id] = wins.get(r.person_id, 0) + (p == 1)
                d += timedelta(days=1)
        rate = {p: wins.get(p, 0) / n for p, n in played.items() if n >= 30}
        if not rate or max(rate.values()) == 0:
            continue
        top = max(rate.values())
        who = sorted(p for p, x in rate.items() if x == top)
        yield Candidate(f"commendation:{start:%Y-%m}", "commendation", day, who, 85,
                        facts={"on": start.isoformat(), "pct": round(top * 100)})



@rule
def rivalries(b: Ledger) -> Iterator[Candidate]:
    """On mondays, the closest head-to-heads of the last thirty days: ten puzzles or more
    filed by both, eight decided, two apart at most. The two most played, nobody in both."""
    for _, day in _closed_days(b):
        if day.weekday() != 0:
            continue
        pairs = []
        for g in b.games:
            if not b.ranked(g):
                continue
            players = sorted(b.players[g])
            for i, a in enumerate(players):
                for c in players[i + 1:]:
                    shared = wa = wc = 0
                    for k in range(1, 31):
                        rs = {r.person_id: r for r in b.by.get((g, day - timedelta(days=k)), [])}
                        if a in rs and c in rs:
                            shared += 1
                            wa += b.better(rs[a], rs[c])
                            wc += b.better(rs[c], rs[a])
                    if shared >= 10 and wa + wc >= 8 and abs(wa - wc) <= 2:
                        lead, trail = (a, c) if wa >= wc else (c, a)
                        pairs.append((shared, g, lead, trail, max(wa, wc), min(wa, wc)))
        taken: set[int] = set()
        for shared, g, lead, trail, w, l in sorted(pairs, key=lambda x: (-x[0], x[1])):
            if {lead, trail} & taken:
                continue
            taken |= {lead, trail}
            yield Candidate(f"rivalry:{day}:{g}:{min(lead, trail)}:{max(lead, trail)}", "rivalry", day, [lead, trail], 55, g,
                            facts={"on": (day - timedelta(days=1)).isoformat(), "w": w, "l": l, "n": shared})
            if len(taken) == 4:
                break


@rule
def attendance(b: Ledger) -> Iterator[Candidate]:
    """All your regulars filed, 5, 10, 20, 30, 50, 100 days running and every 100 after: a
    regular is a game you filed on 10 of the 14 days before, three of them at least. Not
    the whole agenda, which the import filled with every game anyone ever played."""
    def regulars(pid: int, day: date) -> list[str]:
        return [g for g in b.games if pid in b.players[g]
                and sum(day - timedelta(days=j) in b.days(g, pid) for j in range(1, 15)) >= 10]
    for d, report in _closed_days(b):
        for pid in b.nick:
            k = 0
            while True:
                day = d - timedelta(days=k)
                due = regulars(pid, day)
                if len(due) < 3 or any(day not in b.days(g, pid) for g in due):
                    break
                k += 1
            if k in ATTENDANCE or k >= 100 and k % 100 == 0:
                yield Candidate(f"attendance:{pid}:{d}", "attendance", report, [pid], 55 if k < 30 else 65 if k < 100 else 75,
                                facts={"on": d.isoformat(), "n": k})

def _value(b: Ledger, g: str):
    """The metric a game's average is over, if an average of it means something: not a
    ratio, where one 195,288,089× swamps a week."""
    key = reads._key(g)
    m = next((m for m in REGISTRY[g].metrics if m.name == key), None)
    return m if m and not m.optional and m.kind in ("points", "count", "duration", "distance") else None


@rule
def earnings(b: Ledger) -> Iterator[Candidate]:
    """A strong quarter: your average over the last week beats the week before by three
    quarters of the board's spread or more, five puzzles each. Only ever upward; one a day
    for the board, and a fortnight between two about the same person and game."""
    best: dict[date, tuple[float, Candidate]] = {}
    for g, d in b.closed():
        m = _value(b, g)
        everyone = [r.metrics[m.name] for r in b.history[g] if m and r.outcome != "failed" and m.name in r.metrics]
        if not m or len(everyone) < 30 or statistics.pstdev(everyone) == 0:
            continue
        sd = statistics.pstdev(everyone)
        for pid in b.players[g]:
            def over(lo: int, hi: int) -> list[float]:
                return [r.metrics[m.name] for k in range(lo, hi + 1) for r in b.by.get((g, d - timedelta(days=k)), [])
                        if r.person_id == pid and r.outcome != "failed" and m.name in r.metrics]
            cur, prev = over(0, 6), over(7, 13)
            if len(cur) < 5 or len(prev) < 5:
                continue
            was, now = statistics.mean(prev), statistics.mean(cur)
            gain = (now - was if m.better == "high" else was - now) / sd
            report = d + timedelta(days=1)
            if gain >= 0.75 and gain > best.get(report, (0, None))[0] and not _recent(b, "earnings", {pid}, report, 14, g):
                best[report] = (gain, Candidate(f"earnings:{g}:{pid}:{d}", "earnings", report, [pid], 45, g,
                                                facts={"on": d.isoformat(), "was": was, "now": now, "kind": m.kind}))
    for report, (_, c) in sorted(best.items()):  # posted one by one, so the fortnight holds within a run too
        if not _recent(b, "earnings", set(c.subjects), report, 14, c.game) and not b.s.scalar(select(Memo.id).where(
                Memo.board_id == b.board.id, Memo.kind == "earnings", Memo.day == report).limit(1)):
            yield c


@rule
def the_weeklies(b: Ledger) -> Iterator[Candidate]:
    """A weekly game's own news. When a week closes, its champion (or the ones who shared
    it), with how many weeks running; a streak of weeks without missing one; and on the
    last day, a last call if some of the board haven't filed yet."""
    for g in b.weeklies:
        cur = b.current[g]
        for back in (1, 2):
            d = cur - timedelta(days=7 * back)
            rs = b.by.get((g, d), [])
            if len(rs) < 2 or not b.ranked(g):
                continue
            first = [r for p, r in b.placed(g, d) if p == 1]
            if first[0].outcome == "failed":
                continue
            runs = 0
            if len(first) == 1:
                w = first[0].person_id
                while True:
                    top = [r.person_id for p, r in b.placed(g, d - timedelta(days=7 * runs)) if p == 1]
                    if top != [w] or len(b.by.get((g, d - timedelta(days=7 * runs)), [])) < 2:
                        break
                    runs += 1
            yield Candidate(f"champion:{g}:{d}", "champion", d + timedelta(days=7), sorted(r.person_id for r in first),
                            70, g, first[0].id if len(first) == 1 else None,
                            _facts(first[0], d) | {"n": len(rs), "runs": runs, "puzzle": first[0].puzzle_key})
        for d in (cur, cur - timedelta(days=7)):
            for r in b.by.get((g, d), []):
                run = reads.tenure(b.days(g, r.person_id), d, 7)[0]
                if run in FIXTURES or run > 52 and run % 52 == 0:
                    yield Candidate(f"fixture:{g}:{r.person_id}:{d}", "fixture",
                                    local_day(b.viewer, b.now) if d == cur else d + timedelta(days=7),
                                    [r.person_id], 55, g, r.id, {"on": d.isoformat(), "n": run})
        rs = b.by.get((g, cur), [])
        closes = reads.next_reset(g, b.viewer, b.now)
        if rs and closes - b.now <= timedelta(hours=24) and len(rs) < len(b.players[g]):
            yield Candidate(f"lastcall:{g}:{cur}", "lastcall", local_day(b.viewer, b.now), [], 45, g,
                            facts={"on": cur.isoformat(), "n": len(rs), "of": len(b.players[g])})


def _recent(b: Ledger, kind: str, who: set[int], day: date, days: int, game: str | None = None) -> bool:
    """Was this kind of memo about these people (on this game) posted in the last `days` days?"""
    q = select(Memo).where(Memo.board_id == b.board.id, Memo.kind == kind,
                           Memo.day > day - timedelta(days=days), Memo.day <= day)
    if game:
        q = q.where(Memo.game_id == game)
    return any(set(m.subjects) == who for m in b.s.scalars(q))


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
    low: dict[date, int] = {}
    for r in RULES:
        for c in r(b):
            if c.interest <= LOW:
                if c.day not in low:
                    low[c.day] = len(s.scalars(select(Memo.id).where(
                        Memo.board_id == board.id, Memo.day == c.day, Memo.interest <= LOW)).all())
                if low[c.day] >= LOW_A_DAY:
                    continue
            added = len(s.execute(insert(Memo).values(
                board_id=board.id, key=c.key, kind=c.kind, day=c.day, subjects=c.subjects, game_id=c.game,
                result_id=c.result, facts=c.facts, interest=c.interest, created_at=now,
            ).on_conflict_do_nothing(index_elements=["board_id", "key"]).returning(Memo.id)).all())
            new += added
            if added and c.interest <= LOW:
                low[c.day] += 1
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
        if "was" in f and f["was"] == me:
            return f"board record on {game}: {n(p)} took yours, held {_days(f['held'])}. your frame is in storage."
        if "was" in f:
            return f"board record on {game}: {n(p)}, taking it from {n(f['was'])} after {_days(f['held'])}. it will be framed."
        return f"board record on {game}: {n(p)}. it will be framed."
    if k == "pb":
        return f"{n(p)} set a personal best on {game}."
    if k == "highlight":
        if "k" not in f:  # the old kind, one person's, with how many that week
            again = f" that's {f['n']} in a week." if f["n"] > 1 else ""
            return f"{game}: {f['h']} from {n(p)}.{again}"
        names = sorted((n(x) for x in m.subjects), key=lambda x: (x == "you", x))
        gloss = REGISTRY[m.game_id].glossary.get(f["h"]) if m.game_id in REGISTRY else None
        return f"{game}: {f['h']} from {_names(names)}{f', {gloss}' if gloss else ''}."
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
    if k == "precedent":
        return f"precedent on {game}: {f['h']} from {n(p)}, a first for the board. it will be cited."
    if k == "run":
        has = "you've" if p == me else f"{n(p)} has"
        return f"bull run: {has} won {game} {f['n']} days running. the shareholders are delighted."
    if k == "coup":
        w, h = m.subjects
        if me == h:
            return f"coup on {game}: {n(w)} ended your {f['n']}-day run. the board thanks you for your service."
        return f"coup on {game}: {n(w)} ended {pos(h)} {f['n']}-day run. the old guard is out."
    if k == "jinx":
        names = sorted((n(x) for x in m.subjects), key=lambda x: (x == "you", x))
        return f"jinx: {_names(names)} filed the same {game} grid, square for square. compliance has been notified."
    if k == "unanimous":
        return f"unanimous on {game}: all {f['n']} present tied for #1. motion carried."
    if k == "sweep":
        return f"clean sweep: #1 on all {f['n']} of {pos(p)} items. the board demands a recount."
    if k == "rumour":
        s_, lead = m.subjects
        if me == s_:
            return "rumour: you're one daily win off #1 this week. the board smells a takeover."
        if me == lead:
            return f"rumour: {n(s_)} is one daily win behind you this week. watch your back."
        return f"rumour: {n(s_)} is one daily win off {pos(lead)} #1 this week. markets are jittery."
    if k == "champion":
        if len(m.subjects) > 1:
            names = sorted((n(x) for x in m.subjects), key=lambda x: (x == "you", x))
            return f"{game} #{f['puzzle']}: {_names(names)} share the week. the trophy goes on a rota."
        runs = f" {f['runs']} weeks running." if f["runs"] > 1 else ""
        tail = " the board will be insufferable about it." if f["runs"] > 1 and p == me else ""
        return f"{game} #{f['puzzle']} goes to {n(p)}, best of {f['n']} this week.{runs}{tail}"
    if k == "fixture":
        return f"{pos(p)} {f['n']}-week run on {game}. a standing appointment."
    if k == "lastcall":
        return f"last call: {game} closes tonight. {f['n']} of {f['of']} in."
    if k == "buzzer":
        left = f"{f['s']} seconds" if f["s"] < 60 else f"{f['s'] // 60} minute{'s' * (f['s'] >= 120)}"
        tail = " the board respects the hustle." if p == me else ""
        return f"closing bell: {n(p)} filed {game} with {left} to spare.{tail}"
    if k == "night":
        what = game if f["n"] == 1 else f"{f['n']} items"
        return f"night shift: {n(p)} filed {what} at {_clock(f['at'])}. the board does not pay overtime."
    if k == "milestone":
        if p == me:
            return f"you filed the board's {f['n']:,}th result ({game}). the minutes are being bound in leather."
        return f"the board's {f['n']:,}th result, filed by {n(p)} ({game}). the minutes are being bound in leather."
    if k == "quorum":
        return f"quorum: all {f['n']} active members filed. the motion to keep doing this carries."
    if k == "usual":
        who = "" if p == me else f"{n(p)}, "
        return f"the usual: {who}same {game} score {f['n']} days running. the board admires the consistency."
    if k == "commendation":
        month = date.fromisoformat(f["on"]).strftime("%B").lower()
        if len(m.subjects) > 1:
            names = sorted((n(x) for x in m.subjects), key=lambda x: (x == "you", x))
            return f"joint board members of the month for {month}: {_names(names)}. the parking space will be shared."
        return f"board member of the month for {month}: {n(p)}, with a {f['pct']}% win rate. a parking space has been reserved."
    if k == "attendance":
        week = " a full working week." if f["n"] == 5 else ""
        return f"perfect attendance: all of {pos(p)} regulars, {f['n']} days running.{week} hr is drafting a certificate."
    if k == "rivalry":
        lead, trail = m.subjects
        tail = "over the month. it's personal."
        if f["w"] == f["l"]:
            names = sorted((n(x) for x in m.subjects), key=lambda x: (x == "you", x))
            return f"rivalry of the week, {game}: {_names(names)}, level at {f['w']}–{f['l']} {tail}"
        verb = "lead" if lead == me else "leads"
        return f"rivalry of the week, {game}: {n(lead)} {verb} {n(trail)} {f['w']}–{f['l']} {tail}"
    if k == "earnings":
        return (f"strong quarter: {pos(p)} {game} average went from {_fmt(f['kind'], f['was'])} to "
                f"{_fmt(f['kind'], f['now'])} this week. analysts are upgrading.")
    return k


def _fmt(kind: str, v: float) -> str:
    if kind == "duration":
        return f"{int(v) // 60}:{int(v) % 60:02d}"
    if kind == "ratio":
        return f"{v:.2f}×"
    if kind == "distance":
        return f"{v / 1000:.1f}km" if v >= 1000 else f"{v:.0f}m"
    return f"{v:.1f}" if kind == "count" else f"{v:.0f}"


def _days(n: int) -> str:
    return "a day" if n < 2 else f"{n} days"


def _clock(hm: str) -> str:
    h, m = map(int, hm.split(":"))
    return f"{h % 12 or 12}:{m:02d}{'am' if h < 12 else 'pm'}"


def _number(m: Memo) -> str:
    f = m.facts
    return {"takeover": lambda: f"{f['wins']}–{f['was']}", "pip": lambda: f"{f['wins']} wins",
            "tenure": lambda: f"{f['n']}d", "ended": lambda: f"{f['n']}d",
            "highlight": lambda: f"×{f.get('k', f.get('n'))}" if f.get("k", f.get("n", 1)) > 1 else "", "comeback": lambda: "#1",
            "missed": lambda: f"{f['n']}/{f['of']}", "precedent": lambda: "1st", "run": lambda: f"{f['n']} straight",
            "coup": lambda: f"{f['n']}d", "jinx": lambda: f"×{f['n']}", "unanimous": lambda: f"{f['n']}/{f['n']}",
            "sweep": lambda: f"{f['n']}/{f['n']}", "rumour": lambda: f"{f['wins']}–{f['lead']}",
            "buzzer": lambda: f"{f['s']}s" if f["s"] < 60 else f"{f['s'] // 60}m", "night": lambda: _clock(f["at"]),
            "milestone": lambda: f"#{f['n']:,}", "quorum": lambda: f"{f['n']}/{f['n']}", "usual": lambda: f"{f['n']}d",
            "commendation": lambda: f"{f['pct']}%", "rivalry": lambda: f"{f['w']}–{f['l']}", "attendance": lambda: f"{f['n']}d",
            "earnings": lambda: f"{_fmt(f['kind'], f['was'])}→{_fmt(f['kind'], f['now'])}",
            "champion": lambda: f"{f['runs']} wks" if f["runs"] > 1 else "#1", "fixture": lambda: f"{f['n']}wk",
            "lastcall": lambda: f"{f['n']}/{f['of']}"}.get(m.kind, lambda: "")()


def _link(m: Memo, slug: str) -> str:
    if m.kind in ("takeover", "pip", "rumour") or m.game_id is None and m.kind != "commendation":
        return f"/b/{slug}/review?period=week"
    if m.kind == "commendation":
        return f"/b/{slug}/review?period=all"
    if m.kind == "rivalry":
        return f"/b/{slug}/review?period=month&game={m.game_id}"
    if m.kind == "record":
        return f"/b/{slug}/review?period=all&game={m.game_id}"
    return f"/b/{slug}/m/{m.game_id}/{m.facts['on']}"


def _vs(m: Memo, nick: dict[int, str], me: Person) -> str:
    """A rivalry you're in opens the review head to head with the other side."""
    other = [p for p in m.subjects if p != me.id]
    return f"&vs={quote(nick[other[0]])}" if m.kind == "rivalry" and me.id in m.subjects and other[0] in nick else ""


def memo_json(m: Memo, board: Board, nick: dict[int, str], me: Person, dismissed: set[int]) -> dict[str, Any]:
    scored = m.kind in ("record", "pb", "photo", "jinx", "unanimous", "usual", "champion")
    return {
        "id": m.id, "kind": m.kind, "glyph": GLYPH.get(m.kind, "·"), "day": m.day.isoformat(), "game": m.game_id,
        "text": text(m, nick, me.id), "plain": text(m, nick, None),
        "number": _number(m), "score": {"metrics": m.facts["metrics"], "outcome": m.facts["outcome"]} if scored else None,
        "link": _link(m, board.slug) + _vs(m, nick, me), "about": [nick[p] for p in m.subjects if p in nick],
        "me": me.id in m.subjects, "dismissed": m.id in dismissed,
    }


PAIRS = {"takeover", "rumour", "coup", "rivalry"}  # memos about two different people


def rekey(m: Memo, old: int, new: int) -> str:
    """The memo's key with `new` in `old`'s place, as the rules would have keyed it."""
    if m.kind == "milestone":
        return m.key  # its number is the board's count, not a person
    parts = [str(new) if p == str(old) else p for p in re.split(r"([:>])", m.key)]
    if m.kind == "rivalry":
        parts[-3], parts[-1] = sorted((parts[-3], parts[-1]), key=int)
    if m.kind == "jinx":
        parts[-1] = str(min(new if x == old else x for x in m.subjects))
    return "".join(parts)


def move(s: Session, old: int, new: int) -> None:
    """A claimed seat's memos become the claimer's. Where the claimer already has the same
    memo (the rules saw both of them), theirs stays and the seat's goes."""
    for m in s.scalars(select(Memo).where(Memo.subjects.any_() == old)).all():
        key = rekey(m, old, new)
        subjects = list(dict.fromkeys(new if x == old else x for x in m.subjects))
        if (m.kind in PAIRS and len(subjects) < 2) or s.scalar(select(Memo.id).where(
                Memo.board_id == m.board_id, Memo.key == key, Memo.id != m.id)):
            s.delete(m)
            continue
        m.key, m.subjects = key, subjects
    for m in s.scalars(select(Memo).where(Memo.kind == "record", Memo.facts["was"].as_integer() == old)).all():
        m.facts = {**m.facts, "was": new}


def _visible(s: Session, board: Board, q) -> tuple[list[Memo], dict[int, str]]:
    """Memos as they stand: one whose result was withdrawn is hidden, and so is a tenure
    that only looked ended until the missing day was filed late."""
    rows = list(s.scalars(q))
    gone = {i for (i,) in s.execute(select(Result.id).where(
        Result.id.in_([m.result_id for m in rows if m.result_id]), Result.withdrawn_at.is_not(None)))}
    # memos still about a seat claimed before claims moved them (claims are the only way a person goes)
    ids = {x for m in rows for x in m.subjects}
    orphans = ids - set(s.scalars(select(Person.id).where(Person.id.in_(ids)))) if ids else set()
    claimers = set(board.settings.get("claimed", {}).values())
    twins = set(s.scalars(select(Memo.key).where(Memo.board_id == board.id))) if orphans and claimers else set()
    out = []
    for m in rows:
        if m.result_id in gone:
            continue
        if m.kind == "highlight" and "k" not in m.facts and m.day >= REGROUPED:
            continue  # one person's highlight, from before they were grouped; the grouped one says it
        if m.kind == "ended" and s.scalar(select(Result.id).where(
                Result.person_id == m.subjects[0], Result.game_id == m.game_id,
                Result.puzzle_day == date.fromisoformat(m.facts["gap"]), Result.withdrawn_at.is_(None)).limit(1)):
            continue
        if any(rekey(m, o, c) in twins for o in set(m.subjects) & orphans for c in claimers):
            continue  # a claimed seat's, from before claims moved memos; the claimer's own says it
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


def about(s: Session, board: Board, viewer: Person, pid: int, n: int) -> list[dict[str, Any]]:
    """The latest memos about one person, newest first: the member page's."""
    rows, nick = _visible(s, board, select(Memo).where(Memo.board_id == board.id, Memo.subjects.any_() == pid)
                          .order_by(Memo.day.desc(), Memo.interest.desc()).limit(n * 2))
    rows = rows[:n]
    dismissed = _dismissed(s, viewer, [m.id for m in rows])
    return [memo_json(m, board, nick, viewer, dismissed) for m in rows]


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
