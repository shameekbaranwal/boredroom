"""Names people type for themselves and their boards: tidied so they can't hide
characters, reverse text, or pass for someone else on the same board."""
from __future__ import annotations

import unicodedata

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .errors import fail
from .models import Membership

_KEEP = {"‍"}  # the zero-width joiner holds composite emoji together


def clean(value: object, most: int, what: str) -> str:
    """NFKC-normalised, lowercased, without control/format characters (bidi overrides,
    zero-width spaces, NUL), with runs of spaces collapsed. 400 if nothing's left or too long."""
    if not isinstance(value, str):
        fail(400, f"{what} has to be text")
    text = unicodedata.normalize("NFKC", value)
    text = "".join(c for c in text if c in _KEEP or unicodedata.category(c) not in ("Cc", "Cf", "Cs", "Co", "Cn"))
    text = " ".join(text.split()).lower()
    if not 1 <= len(text) <= most:
        fail(400, f"{what} is 1–{most} characters")
    return text


def taken(s: Session, board_id: int, nickname: str, but: int | None = None) -> bool:
    """Does a live member of the board already go by this name?"""
    q = select(Membership.person_id).where(Membership.board_id == board_id, Membership.left_at.is_(None),
                                           func.lower(Membership.nickname) == nickname.lower())
    if but is not None:
        q = q.where(Membership.person_id != but)
    return s.scalar(q) is not None


def free_nickname(s: Session, board_id: int, wanted: str) -> str:
    """`wanted`, or wanted-2, -3… if someone on the board already has it."""
    name, n = wanted, 2
    while taken(s, board_id, name):
        name, n = f"{wanted[:36]}-{n}", n + 1
    return name
