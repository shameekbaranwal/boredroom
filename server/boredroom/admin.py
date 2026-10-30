"""Operator tasks that have no endpoint: deleting a person on request (the privacy
policy's promise), and clearing test data. Run through scripts/forget.py."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .errors import ApiError
from .models import Board, Membership, Paste, Person, Result


@dataclass
class Forgotten:
    username: str
    results: int
    pastes: int
    boards_deleted: list[str]
    chairs_passed: list[str]


def forget(s: Session, username: str) -> Forgotten:
    """Deletes a person and everything that's theirs: results, pastes, seats, agendas and
    tokens (by cascade). A board they chair passes to its longest-serving other member,
    or is deleted if nobody else is on it. Requests they sent for new games stay, unsigned."""
    p = s.scalar(select(Person).where(Person.username == username))
    if p is None:
        raise ApiError(404, f"no one called {username}")
    out = Forgotten(username, s.scalar(select(func.count()).where(Result.person_id == p.id)) or 0,
                    s.scalar(select(func.count()).where(Paste.person_id == p.id)) or 0, [], [])
    for board in s.scalars(select(Board).where(Board.chair_id == p.id)).all():
        heir = s.scalar(select(Membership).where(
            Membership.board_id == board.id, Membership.person_id != p.id, Membership.left_at.is_(None))
            .order_by(Membership.joined_at))
        if heir is None:
            out.boards_deleted.append(board.slug)
            s.execute(delete(Board).where(Board.id == board.id))  # the database cascades the rest
        else:
            board.chair_id, heir.role = heir.person_id, "chair"
            out.chairs_passed.append(f"{board.slug} → {heir.nickname}")
    s.flush()
    s.execute(delete(Person).where(Person.id == p.id))  # seats, agendas, results, pastes, tokens cascade
    s.expire_all()
    return out
