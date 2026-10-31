"""paste -> normalise -> split -> detect -> extract -> key -> check -> results"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from .core import REGISTRY, Block, Context, Game, Result
from .text import normalise


@dataclass
class Unknown:
    """A paste that looks like a result from a game we have no parser for. The app
    turns it into a pre-filled form and an "add this game" request."""
    raw: str
    name: str | None = None
    link: str | None = None
    puzzle: str | None = None
    score: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "link": self.link, "puzzle": self.puzzle,
                "score": self.score, "raw": self.raw}


@dataclass
class Parsed:
    results: list[Result] = field(default_factory=list)
    unknown: list[Unknown] = field(default_factory=list)
    ignored: list[str] = field(default_factory=list)  # game ids dropped on purpose
    note: str = ""  # text that's neither a result nor an unknown game

    def to_dict(self) -> dict[str, Any]:
        return {"results": [r.to_dict() for r in self.results],
                "unknown": [u.to_dict() for u in self.unknown],
                "ignored": self.ignored, "note": self.note}


def parse(text: str, now: datetime | None = None, tz: str = "Asia/Kolkata") -> Parsed:
    from . import games  # noqa: F401  (registers every game)

    ctx = Context(now=now or datetime.now(timezone.utc), tz=tz)
    norm = normalise(text)
    out = Parsed()
    markers = _markers(norm)
    pre = norm[: markers[0][0]] if markers else norm

    for i, (start, game_cls) in enumerate(markers):
        end = markers[i + 1][0] if i + 1 < len(markers) else len(norm)
        chunk = norm[start:end]
        if game_cls.ignore:
            out.ignored.append(game_cls.id)
            continue
        r = _run(game_cls, chunk, ctx)
        out.results.append(r)
        # a headerless result can hide in what looked like this one's comment
        found, r.comment = _fallbacks(r.comment, ctx)
        out.results.extend(found)

    found, pre = _fallbacks(pre, ctx)
    out.results[:0] = found
    pre = pre.strip()
    # text before the first result belongs to it as a comment ("yesterday's krill:")
    if out.results:
        if pre:
            first = out.results[0]
            first.comment = "\n".join(x for x in (pre, first.comment) if x)
    elif pre:
        unk = _unknown(pre)
        if unk:
            out.unknown.append(unk)
        else:
            out.note = pre
    return out


def _markers(text: str) -> list[tuple[int, type[Game]]]:
    found: dict[int, tuple[int, type[Game]]] = {}
    for g in REGISTRY.values():
        for m in re.finditer(g.header, text, re.M):
            prev = found.get(m.start())
            if prev is None or (m.end() - m.start()) > prev[0]:
                found[m.start()] = (m.end() - m.start(), g)
    return sorted(((pos, g) for pos, (_, g) in found.items()), key=lambda x: x[0])


def _run(game_cls: type[Game], chunk: str, ctx: Context, inferred: bool = False) -> Result:
    game = game_cls()
    block = Block(chunk.split("\n"))
    r = Result(game=game_cls.id, raw=chunk.strip(), parser=f"{game_cls.id}@{game_cls.version}")
    if inferred:
        r.warn(f"read as {game_cls.name}", "inferred")
    try:
        game.extract(block, r, ctx)
    except Exception as e:  # a recognised header with a body we can't read
        r.warn(f"couldn't read this {game_cls.name} result ({e.__class__.__name__})", "partial")
    r.comment = block.leftover()
    _check(game_cls, r, ctx)
    return r


def _check(g: type[Game], r: Result, ctx: Context) -> None:
    if r.outcome == "solved":
        for m in g.metrics:
            if not m.optional and m.name not in r.metrics:
                r.warn(f"missing {m.name}", "partial")
    for name, v in r.metrics.items():
        try:
            m = g.metric_def(name)
        except StopIteration:
            continue
        if m.max is not None and v > m.max:
            r.warn(f"{name} {v} is above the maximum {m.max}", "partial")
        if v < 0:
            r.warn(f"{name} can't be negative", "partial")

    cur = g.current(ctx.now, ctx.tz)
    if r.puzzle is None and cur is not None:
        r.puzzle = cur
        r.warn("no puzzle number in the text; assumed today's", "inferred")
    if cur is None or r.puzzle is None:
        r.status = "unknown"
        return
    diff = (r.puzzle - cur).days if isinstance(cur, date) else r.puzzle - cur
    if diff > 1:
        r.status = "ahead"
        r.warn("this puzzle isn't out yet")
    elif diff < 0:
        r.status = "late"
    else:
        r.status = "current"


def _fallbacks(chunk: str, ctx: Context) -> tuple[list[Result], str]:
    if not chunk.strip():
        return [], chunk
    for g in REGISTRY.values():
        if not g.fallback:
            continue
        m = re.search(g.fallback, chunk, re.M)
        if not m:
            continue
        tail = chunk[m.start():]
        if g.links and not any(d in tail.lower() for d in g.links):
            continue
        r = _run(g, tail, ctx, inferred=True)
        return [r], chunk[: m.start()].strip()
    return [], chunk


# starts only where a word does, with bounded labels, so long runs can't backtrack
_URL = re.compile(r"(?<![\w.-])(?:https?://)?(?:www\.)?((?:[a-z0-9-]{1,63}\.){1,10}[a-z]{2,24})(/\S*)?", re.I)
_FRACTION = re.compile(r"\b(\d[\d,.]{0,15})\s*/\s*(\d[\d,]{0,15})\b")  # bounded: "1,1,1,…" can't backtrack
_SCORE = re.compile(r"(?:score|total|points?)\s*[:=]?\s*(\d[\d,.]*)", re.I)
_PUZZLE = re.compile(r"(?:#|№|No\.\s*|Day\s*#?)\s*(\d[\d,]*)")
_SQUARES = re.compile("[\U0001F7E5-\U0001F7EB⬛⬜]{3,}")


def _unknown(text: str) -> Unknown | None:
    """Does this look like a share text at all? A link, a fraction, a puzzle number
    or an emoji grid says yes. Plain chat says no."""
    link = _URL.search(text)
    frac = _FRACTION.search(text)
    score = _SCORE.search(text)
    puzzle = _PUZZLE.search(text)
    grid = _SQUARES.search(text)
    lines = [l for l in text.strip().split("\n") if l.strip()]
    looks_like_share = (
        grid
        or (puzzle and (frac or score))
        or (link and len(lines) >= 2 and (frac or puzzle or score))
        # "Pips #421 Medium" + a time or number on its own line
        or (len(lines) >= 2 and _PUZZLE.search(lines[0]) and re.fullmatch(r"[\d:.,/ ]+\S*", lines[1].strip()))
    )
    if not looks_like_share:
        return None
    first = lines[0][:200]
    name = None
    if not _URL.match(first.strip()):
        name = re.split(r"\s+(?:#|№|No\.|Day\b|-|—|:|\d)|:", first, maxsplit=1)[0]
        name = re.sub(r"[^\w\s'&.-]", "", name).strip() or None
    suggestion = frac.group(0).replace(" ", "") if frac else (score.group(1) if score else None)
    return Unknown(
        raw=text.strip(),
        name=(name or (link.group(1).split(".")[-2] if link else None)),
        link=link.group(1).lower() if link else None,
        puzzle=puzzle.group(1).replace(",", "") if puzzle else None,
        score=suggestion,
    )
