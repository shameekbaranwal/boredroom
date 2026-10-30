"""Turns pasted share texts into results. See docs/PARSER.md."""
from .core import REGISTRY, Field, Game, Metric, Reset, Result
from .forward import forward_text
from .pipeline import Parsed, Unknown, parse
from .rank import compare, rank

__all__ = ["REGISTRY", "Field", "Game", "Metric", "Parsed", "Reset", "Result", "Unknown",
           "compare", "forward_text", "parse", "rank"]
