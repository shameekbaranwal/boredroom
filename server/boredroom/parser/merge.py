"""A member pasting the same puzzle again.

Often it's the same play with more detail: the wiki game is shared once with just
steps and time, then again with the route (20 times in the soup export, usually with
the clock a second or a few further on). That merges silently. A different result
(a re-do, a re-play) is a conflict, and the app asks "replace?".
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Literal

from .core import REGISTRY, Result

Kind = Literal["duplicate", "enrich", "conflict"]


@dataclass
class Merge:
    kind: Kind
    result: Result  # what to keep: merged for enrich, the original otherwise
    added: list[str]  # field names the new paste brought


def same_play(a: Result, b: Result) -> bool:
    """Same game, puzzle and outcome, and every metric both have agrees within the
    game's tolerance (wiki time: a few seconds between copies of one share)."""
    if (a.game, a.puzzle, a.outcome) != (b.game, b.puzzle, b.outcome):
        return False
    tol = REGISTRY[a.game].tolerance
    for name in a.metrics.keys() & b.metrics.keys():
        if abs(a.metrics[name] - b.metrics[name]) > tol.get(name, 0):
            return False
    return True


def merge(old: Result, new: Result) -> Merge:
    if not same_play(old, new):
        return Merge("conflict", old, [])

    have = {f.name for f in old.fields}
    added = [f for f in new.fields if f.name not in have]
    gained_metrics = new.metrics.keys() - old.metrics.keys()
    if not added and not gained_metrics:
        return Merge("duplicate", old, [])

    m = deepcopy(old)
    # the score the board already saw stays; only missing metrics are filled in
    for name in gained_metrics:
        m.metrics[name] = new.metrics[name]
    m.fields.extend(deepcopy(added))
    m.highlights.extend(h for h in new.highlights if h not in m.highlights)
    m.extras = {**new.extras, **old.extras}
    if new.comment and new.comment not in m.comment:
        m.comment = "\n".join(x for x in (m.comment, new.comment) if x)
    # forward the richer text from now on
    m.raw = new.raw
    if new.confidence == "exact":
        m.confidence = "exact"
        m.warnings = list(new.warnings)
    return Merge("enrich", m, [f.name for f in added] + sorted(gained_metrics))
