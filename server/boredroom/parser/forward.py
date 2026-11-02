"""The text "send to soup" passes on to WhatsApp.

Results with a spoiler field are wrapped the way soup already does it by hand: a
"[... spoiler]" line, then enough invisible padding that WhatsApp folds the rest
under "read more".
"""
from __future__ import annotations

from .core import REGISTRY, Result

ZWSP = "​"
# the share sheet cuts a message at 4096 bytes (utf-8), so the padding fills what's left of that
LIMIT = 4000


def _score(r: Result) -> str:
    """The result in a few words, none of them a spoiler: "6 steps · 3:23"."""
    out = []
    for m in REGISTRY[r.game].metrics:
        v = r.metrics.get(m.name)
        if v is None:
            continue
        if m.kind == "duration":
            out.append(f"{int(v) // 60}:{int(v) % 60:02d}")
        elif m.kind == "count":
            out.append(f"{v:g} {m.name[:-1] if v == 1 and m.name.endswith('s') else m.name}")
        else:
            out.append(f"{v:g} {m.name}")
    return " · ".join(out) if r.outcome != "failed" else "failed"


def forward_text(r: Result) -> str:
    text = r.raw
    hidden = [f.name for f in r.fields if f.visibility == "spoiler"]
    if hidden:
        # the score shows; only the spoiler waits under "read more", so the message never looks empty
        name = REGISTRY[r.game].name
        score = _score(r)
        line = " · ".join(x for x in (score, f"read more for the {hidden[0]}") if x)
        head = f"[{name} spoiler] {line}\n\n\n"
        room = (LIMIT - len(head.encode()) - len(text.encode())) // len(ZWSP.encode())
        return f"{head}{ZWSP * max(room, 0)}{text}"
    return text
