"""The result model and the base class every game parser extends.

A game is a subclass of `Game` that declares its metadata as class attributes and
implements `extract()`. Subclasses register themselves on import, so adding a game
means adding one module under `games/`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any, ClassVar, Literal
from zoneinfo import ZoneInfo

Kind = Literal["points", "count", "ratio", "duration", "distance", "grade", "position"]
Better = Literal["high", "low"]
Visibility = Literal["public", "detail", "spoiler"]
Outcome = Literal["solved", "failed", "played"]
Confidence = Literal["exact", "inferred", "partial"]


@dataclass(frozen=True)
class Metric:
    """A rankable value a game produces, e.g. points out of 1000, higher is better."""
    name: str
    kind: Kind
    better: Better
    max: float | None = None
    unit: str | None = None
    optional: bool = False  # missing is fine (minute cryptic time), not a partial parse


@dataclass(frozen=True)
class Reset:
    """When a new puzzle goes live. `tz=None` means the player's own midnight. A weekly
    game sets `weekday` (0 is Monday): its puzzle goes live that day and lasts the week."""
    tz: str | None = None
    at: time = time(0, 0)
    weekday: int | None = None

    @property
    def every(self) -> int:
        """Days between two puzzles."""
        return 1 if self.weekday is None else 7

    def game_day(self, now: datetime, member_tz: str) -> date:
        """The day whose puzzle is current at `now`: for a weekly game, the day its week began."""
        local = now.astimezone(ZoneInfo(self.tz or member_tz))
        day = (local - timedelta(hours=self.at.hour, minutes=self.at.minute)).date()
        return day if self.weekday is None else day - timedelta(days=(day.weekday() - self.weekday) % 7)


@dataclass
class Field:
    name: str
    value: Any
    visibility: Visibility = "detail"


@dataclass
class Result:
    game: str
    puzzle: int | date | str | None = None
    outcome: Outcome = "solved"
    metrics: dict[str, float] = field(default_factory=dict)
    fields: list[Field] = field(default_factory=list)
    highlights: list[str] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)
    comment: str = ""
    raw: str = ""
    parser: str = ""
    confidence: Confidence = "exact"
    warnings: list[str] = field(default_factory=list)
    status: Literal["current", "late", "ahead", "unknown"] = "unknown"

    # helpers extractors use
    def metric(self, name: str, value: float | None) -> None:
        if value is not None:
            self.metrics[name] = value

    def detail(self, name: str, value: Any, visibility: Visibility = "detail") -> None:
        if value not in (None, "", []):
            self.fields.append(Field(name, value, visibility))

    def highlight(self, name: str) -> None:
        if name not in self.highlights:
            self.highlights.append(name)

    def warn(self, message: str, confidence: Confidence | None = None) -> None:
        self.warnings.append(message)
        if confidence == "partial" or (confidence == "inferred" and self.confidence == "exact"):
            self.confidence = confidence

    def field_value(self, name: str) -> Any:
        return next((f.value for f in self.fields if f.name == name), None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "game": self.game,
            "puzzle": self.puzzle.isoformat() if isinstance(self.puzzle, date) else self.puzzle,
            "status": self.status,
            "outcome": self.outcome,
            "metrics": self.metrics,
            "fields": [{"name": f.name, "value": f.value, "visibility": f.visibility} for f in self.fields],
            "highlights": self.highlights,
            "extras": self.extras,
            "comment": self.comment,
            "confidence": self.confidence,
            "warnings": self.warnings,
            "parser": self.parser,
        }


class Block:
    """The lines of one result. Extractors read lines through it, and every line they
    match is marked used; the unused lines after the result become its comment."""

    def __init__(self, lines: list[str]):
        self.lines = lines
        self.used: set[int] = set()

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    def find(self, pattern: str | re.Pattern, start: int = 0) -> re.Match | None:
        """First line matching `pattern` (searched, not anchored), marked used."""
        rx = re.compile(pattern) if isinstance(pattern, str) else pattern
        for i in range(start, len(self.lines)):
            m = rx.search(self.lines[i])
            if m:
                self.used.add(i)
                return m
        return None

    def find_all(self, pattern: str | re.Pattern) -> list[re.Match]:
        rx = re.compile(pattern) if isinstance(pattern, str) else pattern
        out = []
        for i, line in enumerate(self.lines):
            m = rx.search(line)
            if m:
                self.used.add(i)
                out.append(m)
        return out

    def rows(self, alphabet: str, min_len: int = 1) -> list[list[str]]:
        """Consecutive grid rows made only of emoji from `alphabet` (spaces ignored).
        Returns each row as a list of emoji. Stops at the first non-grid line after
        the grid starts."""
        from .text import emoji_cells

        allowed = set(emoji_cells(alphabet))
        grid: list[list[str]] = []
        for i, line in enumerate(self.lines):
            cells = emoji_cells(line)
            if len(cells) >= min_len and all(c in allowed for c in cells):
                grid.append(cells)
                self.used.add(i)
            elif grid and line.strip():
                break
        return grid

    def use_links(self, domain: str) -> bool:
        hit = False
        for i, line in enumerate(self.lines):
            if domain.lower() in line.lower():
                self.used.add(i)
                hit = True
        return hit

    def leftover(self) -> str:
        """Unused, non-blank lines after the last used line."""
        last = max(self.used, default=-1)
        rest = [l for l in self.lines[last + 1:] if l.strip()]
        return "\n".join(rest).strip()


REGISTRY: dict[str, type["Game"]] = {}


class Game:
    """Declare metadata as class attributes; implement `extract`."""

    id: ClassVar[str]
    name: ClassVar[str]
    version: ClassVar[int] = 1
    # start marker: a regex matched at the start of a line (re.M). It may span lines.
    header: ClassVar[str]
    # domains that confirm the game when the header is missing (see `fallback`)
    links: ClassVar[tuple[str, ...]] = ()
    # where "play" opens, when the game isn't at https://links[0] (that's often the home page)
    play: ClassVar[str | None] = None
    # optional start marker used only in text no header claimed; results are `inferred`
    fallback: ClassVar[str | None] = None
    key: ClassVar[Literal["number", "date", "pair"]] = "number"
    # for number keys: (puzzle number, the day it was current) — a known point
    anchor: ClassVar[tuple[int, date] | None] = None
    reset: ClassVar[Reset] = Reset()
    metrics: ClassVar[tuple[Metric, ...]] = ()
    # metric names in ranking order; outcome always ranks first. Empty = not ranked.
    ranker: ClassVar[tuple[str, ...]] = ()
    # header matched -> drop the block silently (e.g. connections bonus puzzles)
    ignore: ClassVar[bool] = False
    # how far a metric may differ between two pastes of the same play (see merge.py)
    tolerance: ClassVar[dict[str, float]] = {}

    @classmethod
    def play_url(cls) -> str | None:
        return cls.play or (f"https://{cls.links[0]}" if cls.links else None)

    def __init_subclass__(cls, **kw):
        super().__init_subclass__(**kw)
        if "id" in cls.__dict__:
            if cls.id in REGISTRY:
                raise ValueError(f"duplicate game id {cls.id}")
            REGISTRY[cls.id] = cls

    # -- to implement ------------------------------------------------------------
    def extract(self, block: Block, r: Result, ctx: "Context") -> None:
        raise NotImplementedError

    # -- shared behaviour --------------------------------------------------------
    @classmethod
    def metric_def(cls, name: str) -> Metric:
        return next(m for m in cls.metrics if m.name == name)

    @classmethod
    def ranked(cls) -> bool:
        return bool(cls.ranker)

    @classmethod
    def weekly(cls) -> bool:
        return cls.reset.weekday is not None

    @classmethod
    def week_of(cls, day: date) -> date:
        """The game day a date belongs to: itself, or for a weekly game the day its week began."""
        w = cls.reset.weekday
        return day if w is None else day - timedelta(days=(day.weekday() - w) % 7)

    @classmethod
    def puzzle_day(cls, puzzle: int | date | str | None) -> date | None:
        """The day a puzzle belongs to. None for page-pair keys (the wiki game),
        whose day is set by the first filing (see the server)."""
        if isinstance(puzzle, date):
            return puzzle
        if cls.key == "number" and cls.anchor and isinstance(puzzle, int):
            n, d = cls.anchor
            return d + timedelta(days=(puzzle - n) * cls.reset.every)
        return None

    @classmethod
    def current(cls, now: datetime, member_tz: str) -> int | date | None:
        day = cls.reset.game_day(now, member_tz)
        if cls.key == "date":
            return day
        if cls.key == "number" and cls.anchor:
            n, d = cls.anchor
            return n + (day - d).days // cls.reset.every
        return None


@dataclass
class Context:
    now: datetime
    tz: str

    @property
    def today(self) -> date:
        return self.now.astimezone(ZoneInfo(self.tz)).date()
