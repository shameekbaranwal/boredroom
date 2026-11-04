"""Boards, membership, the library and personal agendas."""
from __future__ import annotations

import re
import secrets
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from . import claims, invites, names
from .errors import fail
from .models import Agenda, Board, BoardGame, Invite, Membership, Paste, Person, Result, utcnow
from .parser import REGISTRY
from .reads import my_order


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:50] or "board"


def create_board(s: Session, chair: Person, name: str) -> Board:
    name = names.clean(name, 60, "a board's name")
    base = slug = slugify(name)
    # taken (or a name with no letters to slug, which all become "board"): a random suffix,
    # so finding a free slug is one or two lookups, never a count up through every board
    while s.scalar(select(Board.id).where(Board.slug == slug)):
        slug = f"{base[:44]}-{secrets.token_hex(2)}"
    board = Board(name=name, slug=slug, chair_id=chair.id,
                  settings={"late_filing": True, "join": "link"})
    s.add(board)
    s.flush()
    s.add(Membership(board_id=board.id, person_id=chair.id, nickname=chair.username, role="chair"))
    invites.create(s, board, chair)
    return board


def get_board(s: Session, slug: str, person: Person) -> tuple[Board, Membership]:
    """The board and the person's membership in it; 404 for boards they're not on."""
    board = s.scalar(select(Board).where(Board.slug == slug))
    m = board and s.get(Membership, (board.id, person.id))
    if not board or not m or m.left_at is not None:
        fail(404, "no such board")
    return board, m


def join(s: Session, person: Person, code: str, claim: str | None = None) -> Board:
    """Takes a seat on the invite's board: a new one, or (`claim`) an imported one, whose
    name and history become yours."""
    board = invites.lookup(s, code).board
    m = s.get(Membership, (board.id, person.id))
    if claim and (m is None or m.left_at is not None):
        claims.claim(s, board, person, claim)
    elif m is None:
        s.add(Membership(board_id=board.id, person_id=person.id, nickname=names.free_nickname(s, board.id, person.username)))
    elif m.left_at is not None:
        m.left_at = None
    return board


def heir(s: Session, board: Board, leaving: Person) -> Membership | None:
    """Who takes the chair when its holder goes: the longest-serving person still on the
    board, else the longest-serving imported seat."""
    rest = s.scalars(select(Membership).join(Person, Person.id == Membership.person_id).where(
        Membership.board_id == board.id, Membership.person_id != leaving.id, Membership.left_at.is_(None))
        .order_by(Person.kind == "placeholder", Membership.joined_at)).all()
    return rest[0] if rest else None


def leave(s: Session, board: Board, person: Person) -> bool:
    """Gives up a seat. A seat claimed from the chat history goes back to being unclaimed;
    the chair passes on. The last one out closes the board. Returns whether it did."""
    m = s.get(Membership, (board.id, person.id))
    if m is None or m.left_at is not None:
        fail(404, "no such board")
    claims.unclaim(s, board, person)
    if board.chair_id == person.id:
        h = heir(s, board, person)
        if h is None:
            s.execute(delete(Board).where(Board.id == board.id))  # the database cascades the rest
            s.expire_all()
            return True
        board.chair_id, h.role = h.person_id, "chair"
    m.role, m.left_at = "member", utcnow()
    s.execute(delete(Agenda).where(Agenda.board_id == board.id, Agenda.person_id == person.id))
    s.execute(update(Invite).where(Invite.board_id == board.id, Invite.created_by == person.id,
                                   Invite.revoked_at.is_(None)).values(revoked_at=utcnow()))
    s.flush()
    return False


def leaving_json(s: Session, board: Board, person: Person) -> dict[str, Any]:
    """What leaving `board` would do: the seat that goes back, who takes the chair."""
    names = [n for n, pid in board.settings.get("claimed", {}).items() if pid == person.id]
    h = heir(s, board, person) if board.chair_id == person.id else None
    imported = 0
    if names:
        ids = set(s.scalars(select(Paste.id).where(Paste.person_id == person.id, Paste.source == "import")))
        imported = sum(1 for r in s.scalars(select(Result).where(Result.person_id == person.id))
                       if r.paste_ids and all(p in ids for p in r.paste_ids))
    others = sum(1 for m in board.memberships if m.left_at is None and m.person_id != person.id)
    return {"slug": board.slug, "name": board.name, "chair": board.chair_id == person.id,
            "claimed": {"nickname": names[0], "results": imported} if names else None,
            "heir": h.nickname if h else None, "alone": others == 0}


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


def _others_playing(s: Session, board: Board, person_id: int, game_id: str) -> int:
    return s.scalar(select(func.count()).select_from(Agenda).where(
        Agenda.board_id == board.id, Agenda.game_id == game_id, Agenda.person_id != person_id)) or 0


def removable(s: Session, board: Board, m: Membership, bg: BoardGame) -> bool:
    """The chair can take any game off. Whoever added one can take it back off while
    nobody else has it on their agenda, so a mis-tap doesn't need the chair."""
    return m.role == "chair" or (bg.added_by == m.person_id and not _others_playing(s, board, m.person_id, bg.game_id))


def remove_from_library(s: Session, board: Board, m: Membership, game_id: str) -> None:
    bg = s.get(BoardGame, (board.id, game_id))
    if bg is None:
        return
    if not removable(s, board, m, bg):
        fail(403, "only the chair can take that game off now: others play it")
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


def set_nudge(s: Session, board: Board, person: Person, game_id: str, on: bool) -> None:
    """A push an hour before the game resets, if you haven't filed. Only for games on your agenda."""
    row = s.get(Agenda, (board.id, person.id, game_id))
    if row is None:
        fail(409, "put it on your agenda first")
    row.nudge = on


def set_nudges(s: Session, board: Board, person: Person, on: bool) -> None:
    """Every game on your agenda here nudges, or none does."""
    for row in s.scalars(select(Agenda).where(Agenda.board_id == board.id, Agenda.person_id == person.id)):
        row.nudge = on


def set_order(s: Session, board: Board, person: Person, games: list[str]) -> None:
    """Places your agenda games in this order. Games left out keep their turn after these,
    in the order they had; games not on your agenda are ignored."""
    rows = {a.game_id: a for a in s.scalars(select(Agenda).where(Agenda.board_id == board.id, Agenda.person_id == person.id))}
    placed = list(dict.fromkeys(g for g in games if g in rows))
    rest = [g for g in my_order(s, board, person.id) if g not in placed]
    for n, g in enumerate(placed + rest):
        rows[g].position = n


def agenda_of(s: Session, board: Board, person: Person) -> list[str]:
    return list(s.scalars(select(Agenda.game_id).where(
        Agenda.board_id == board.id, Agenda.person_id == person.id).order_by(Agenda.game_id)))


def board_json(s: Session, board: Board, m: Membership) -> dict[str, Any]:
    members = [x for x in board.memberships if x.left_at is None]
    agendas: dict[int, list[str]] = {}
    nudges: list[str] = []
    for a in s.scalars(select(Agenda).where(Agenda.board_id == board.id)):
        agendas.setdefault(a.person_id, []).append(a.game_id)
        if a.nudge and a.person_id == m.person_id:
            nudges.append(a.game_id)
    # what each member has on file here: their results for the board's games
    lib = [bg.game_id for bg in board.library]
    filed = dict(s.execute(select(Result.person_id, func.count()).where(
        Result.person_id.in_([x.person_id for x in members]), Result.game_id.in_(lib),
        Result.withdrawn_at.is_(None)).group_by(Result.person_id)).all()) if lib and members else {}
    out = {
        "slug": board.slug, "name": board.name,
        "settings": {k: v for k, v in board.settings.items() if k != "claimed"},  # person ids stay here
        "you": {"nickname": m.nickname, "role": m.role, "agenda": sorted(agendas.get(m.person_id, [])),
                "claimed": m.person_id in board.settings.get("claimed", {}).values(),  # one seat each
                "digest": m.digest, "nudges": sorted(nudges),
                "order": my_order(s, board, m.person_id)},  # your agenda in your own order
        "members": [{"nickname": x.nickname, "username": x.person.username, "role": x.role,
                     "kind": x.person.kind, "joined_at": x.joined_at.isoformat(),
                     "games": len(agendas.get(x.person_id, [])), "results": filed.get(x.person_id, 0)}
                    for x in sorted(members, key=lambda x: x.nickname)],
        "library": [{"game": bg.game_id, "name": REGISTRY[bg.game_id].name, "rules": bg.rules,
                     "players": sum(bg.game_id in g for g in agendas.values()),
                     "removable": m.role == "chair" or (bg.added_by == m.person_id and not any(
                         bg.game_id in g for pid, g in agendas.items() if pid != m.person_id))}
                    for bg in sorted(board.library, key=lambda b: b.game_id)],
    }
    out["leaving"] = leaving_json(s, board, m.person)
    inv = invites.current(s, board, m.person)  # each member hands out their own
    out["invite"] = {"code": inv.code, "expires_at": inv.expires_at.isoformat() if inv.expires_at else None}
    return out
