"""Shared helpers: normalising pastes, numbers, dates, durations and emoji grids."""
from __future__ import annotations

import re
from datetime import date, timedelta

# zero-width and bidi marks people (and WhatsApp) put in pastes. U+200D (zero-width
# joiner) is kept: it holds composite emoji like 🤷‍♂️ together.
_INVISIBLE = re.compile("[​‌‎‏‪-‮⁠⁦-⁩﻿]")
_EDITED = re.compile(r"[ \t]*<This message was edited>[ \t]*$", re.M)
_ANGLE_LINK = re.compile(r"<(https?://[^>\s]+|[\w.-]+\.\w{2,}/[^>\s]*)>")
_URL = re.compile(r"https?://\S+")
_TRACKING_PARAMS = re.compile(r"^(?:r|si|ref|utm_[a-z]+)$")
_SPOILER_WRAPPER = re.compile(r"^[ \t]*\[[^\]\n]{0,80}spoiler[^\]\n]{0,80}\][ \t]*$", re.I | re.M)


def normalise(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _INVISIBLE.sub("", text)
    text = _EDITED.sub("", text)
    text = _ANGLE_LINK.sub(r"\1", text)
    text = _URL.sub(_strip_tracking, text)
    text = _SPOILER_WRAPPER.sub("", text)
    lines = [l.rstrip() for l in text.split("\n")]
    return "\n".join(lines).strip("\n")


def _strip_tracking(m: re.Match) -> str:
    """Drop referral and utm parameters, keep any others."""
    url = m.group(0)
    base, sep, query = url.partition("?")
    if not sep:
        return url
    kept = [p for p in query.split("&") if p and not _TRACKING_PARAMS.match(p.split("=")[0])]
    return base + ("?" + "&".join(kept) if kept else "")


def number(s: str | None) -> float | None:
    """'1,953' -> 1953, '1.20' -> 1.2. Returns int when whole."""
    if s is None:
        return None
    s = s.replace(",", "").strip()
    try:
        v = float(s)
    except ValueError:
        return None
    return int(v) if v.is_integer() and "." not in s else v


def duration(s: str | None) -> int | None:
    """'02:09' / '1:02:09' / '1m 7s' / '45s' -> seconds."""
    if not s:
        return None
    s = s.strip()
    if ":" in s:
        parts = [int(p) for p in s.split(":")]
        secs = 0
        for p in parts:
            secs = secs * 60 + p
        return secs
    m = re.fullmatch(r"(?:(\d+)h\s*)?(?:(\d+)m\s*)?(?:(\d+)s)?", s)
    if not m or not any(m.groups()):
        return None
    h, mi, se = (int(g or 0) for g in m.groups())
    return h * 3600 + mi * 60 + se


MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def month(name: str) -> int | None:
    return MONTHS.get(name[:3].lower())


def nearest_year(m: int, d: int, around: date) -> date | None:
    """A date with no year: pick the year that puts it nearest to `around`, never
    more than one day after it (MapTap shares 'October 12')."""
    best = None
    for y in (around.year - 1, around.year, around.year + 1):
        try:
            cand = date(y, m, d)
        except ValueError:
            continue
        if cand > around + timedelta(days=1):
            continue
        if best is None or abs((cand - around).days) < abs((best - around).days):
            best = cand
    return best


def make_date(y: int, m: int | None, d: int) -> date | None:
    try:
        return date(y, m, d) if m else None
    except ValueError:
        return None


# emoji handling ----------------------------------------------------------------
_VS = "️"
_KEYCAP = "⃣"


def emoji_cells(s: str) -> list[str]:
    """Split a grid row into emoji, ignoring spaces and variation selectors.
    Keeps ZWJ sequences and skin-tone modifiers attached to their base."""
    s = s.replace(_VS, "")
    cells: list[str] = []
    for ch in s:
        if ch.isspace():
            continue
        if cells and (ch == "‍" or cells[-1].endswith("‍") or 0x1F3FB <= ord(ch) <= 0x1F3FF):
            cells[-1] += ch
        else:
            cells.append(ch)
    return cells


def count(cells: list[str] | list[list[str]], which: str) -> int:
    flat = [c for row in cells for c in (row if isinstance(row, list) else [row])]
    targets = set(emoji_cells(which))
    return sum(1 for c in flat if c in targets)
