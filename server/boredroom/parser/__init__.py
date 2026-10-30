"""Turns pasted share texts into results. See docs/PARSER.md."""
from .core import REGISTRY, Field, Game, Metric, Reset, Result
from .forward import forward_text
from .merge import Merge, merge, same_play
from .pipeline import Parsed, Unknown, parse
from .rank import compare, rank

__all__ = ["REGISTRY", "Field", "Game", "Merge", "Metric", "Parsed", "Reset", "Result", "Unknown",
           "compare", "forward_text", "merge", "parse", "rank", "same_play"]
