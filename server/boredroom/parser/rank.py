"""Order results for one puzzle by the game's ranker. Ties share a place (1, =2, =2, 4)."""
from __future__ import annotations

from functools import cmp_to_key

from .core import REGISTRY, Result

_OUTCOME = {"solved": 0, "played": 0, "failed": 1}


def compare(a: Result, b: Result, ranker: tuple[str, ...] | None = None) -> int:
    """<0 if a ranks above b. A metric only one of them has is skipped for the pair."""
    g = REGISTRY[a.game]
    order = ranker if ranker is not None else g.ranker
    d = _OUTCOME[a.outcome] - _OUTCOME[b.outcome]
    if d:
        return d
    for name in order:
        va, vb = a.metrics.get(name), b.metrics.get(name)
        if va is None or vb is None or va == vb:
            continue
        better_high = g.metric_def(name).better == "high"
        return (-1 if va > vb else 1) * (1 if better_high else -1)
    return 0


def rank(results: list[Result], ranker: tuple[str, ...] | None = None) -> list[tuple[int, Result]]:
    """[(place, result)] best first. Unranked games return everyone at place 0."""
    if not results:
        return []
    g = REGISTRY[results[0].game]
    if not (ranker or g.ranker):
        return [(0, r) for r in results]
    ordered = sorted(results, key=cmp_to_key(lambda a, b: compare(a, b, ranker)))
    out: list[tuple[int, Result]] = []
    for i, r in enumerate(ordered):
        if i and compare(ordered[i - 1], r, ranker) == 0:
            out.append((out[-1][0], r))
        else:
            out.append((i + 1, r))
    return out
