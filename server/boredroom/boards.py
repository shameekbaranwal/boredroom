"""Boards, membership, the library and personal agendas."""
from __future__ import annotations

import re
import secrets
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .errors import fail
from .models import Agenda, Board, BoardGame, Membership, Person
from .parser import REGISTRY


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:50] or "board"


def create_board(s: Session, chair: Person, name: str) -> Board:
    name = name.strip().lower()
    if not 1 <= len(name) <= 60:
        fail(400, "board names are 1–60 characters")
    base = slug = slugify(name)
    n = 2
    while s.scalar(select(Board.id).where(Board.slug == slug)):
        slug, n = f"{base}-{n}", n + 1
    board = Board(name=name, slug=slug, chair_id=chair.id, invite_code=secrets.token_urlsafe(9),
                  settings={"late_filing": True, "join": "link"})
    s.add(board)
    s.flush()
    s.add(Membership(board_id=board.id, person_id=chair.id, nickname=chair.username, role="chair"))
    return board


def get_board(s: Session, slug: str, person: Person) -> tuple[Board, Membership]:
    """The board and the person's membership in it; 404 for boards they're not on."""
    board = s.scalar(select(Board).where(Board.slug == slug))
    m = board and s.get(Membership, (board.id, person.id))
    if not board or not m or m.left_at is not None:
        fail(404, "no such board")
    return board, m


def join(s: Session, person: Person, code: str) -> Board:
    board = s.scalar(select(Board).where(Board.invite_code == code))
    if not board:
        fail(404, "that invite link doesn't work")
    m = s.get(Membership, (board.id, person.id))
    if m is None:
        s.add(Membership(board_id=board.id, person_id=person.id, nickname=person.username))
    elif m.left_at is not None:
        m.left_at = None
    return board


def check_game(game_id: str) -> None:
    g = REGISTRY.get(game_id)
    if g is None or g.ignore:
        fail(404, f"no game called {game_id}")


def add_to_library(s: Session, board: Board, person: Person, game_id: str) -> BoardGame:
    check_game(game_id)
    bg = s.get(BoardGame, (board.id, game_id))
    if bg is None:
        bg = BoardGame(board_id=board.id, game_id=game_id, added_by=person.id, rules={})
        s.add(bg)
        s.flush()
    return bg


def remove_from_library(s: Session, board: Board, m: Membership, game_id: str) -> None:
    if m.role != "chair":
        fail(403, "only the chair can remove games from the library")
    bg = s.get(BoardGame, (board.id, game_id))
    if bg:
        s.delete(bg)  # agendas cascade


def set_agenda(s: Session, board: Board, person: Person, game_id: str, on: bool) -> None:
    """Add or drop a game from your agenda. Adding a game the board doesn't have yet
    adds it to the library too ("+ add a game")."""
    row = s.get(Agenda, (board.id, person.id, game_id))
    if on and row is None:
        add_to_library(s, board, person, game_id)
        s.add(Agenda(board_id=board.id, person_id=person.id, game_id=game_id))
    elif not on and row is not None:
        s.delete(row)


def agenda_of(s: Session, board: Board, person: Person) -> list[str]:
    return list(s.scalars(select(Agenda.game_id).where(
        Agenda.board_id == board.id, Agenda.person_id == person.id).order_by(Agenda.game_id)))


def board_json(s: Session, board: Board, m: Membership) -> dict[str, Any]:
    members = [x for x in board.memberships if x.left_at is None]
    agendas: dict[int, list[str]] = {}
    for a in s.scalars(select(Agenda).where(Agenda.board_id == board.id)):
        agendas.setdefault(a.person_id, []).append(a.game_id)
    out = {
        "slug": board.slug, "name": board.name, "settings": board.settings,
        "you": {"nickname": m.nickname, "role": m.role, "agenda": sorted(agendas.get(m.person_id, []))},
        "members": [{"nickname": x.nickname, "role": x.role, "kind": x.person.kind,
                     "games": len(agendas.get(x.person_id, []))}
                    for x in sorted(members, key=lambda x: x.nickname)],
        "library": [{"game": bg.game_id, "name": REGISTRY[bg.game_id].name, "rules": bg.rules,
                     "players": sum(bg.game_id in g for g in agendas.values())}
                    for bg in sorted(board.library, key=lambda b: b.game_id)],
    }
    out["invite_code"] = board.invite_code  # joining by link is open to any member's invite
    return out
