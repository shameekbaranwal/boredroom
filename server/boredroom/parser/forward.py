"""The text "send to soup" passes on to WhatsApp.

Results with a spoiler field are wrapped the way soup already does it by hand: a
"[... spoiler]" line, then enough invisible padding that WhatsApp folds the rest
under "read more".
"""
from __future__ import annotations

from .core import REGISTRY, Result

PADDING = "​" * 4000


def forward_text(r: Result) -> str:
    text = r.raw
    if any(f.visibility == "spoiler" for f in r.fields):
        name = REGISTRY[r.game].name
        return f"[{name} spoiler]\n\n\n{PADDING}{text}"
    return text
