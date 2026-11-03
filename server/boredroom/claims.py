"""Placeholder seats: members imported from a chat export, waiting for the real person to
claim them (docs/SERVER.md choice 6). Claiming moves the placeholder's history, agendas
and board seats onto the claimer, then deletes the placeholder.

A guest seat signing in to a google account that already exists folds in the same way
(`merge_guest`), so the guest's history and boards aren't left behind."""
from __future__ import annotations

import re

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from . import memos
from .errors import fail
from .models import (Agenda, AuthToken, Board, BoardGame, Feedback, GameRequest, Invite, Membership, MemoDismissal,
                     Paste, Person, Result, Skip)


def placeholder_username(s: Session, name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:24] or "member"
    username, n = base, 2
    while s.scalar(select(Person.id).where(Person.username == username)):
        username, n = f"{base}-{n}", n + 1
    return username


def add_placeholder(s: Session, board: Board, nickname: str, tz: str) -> Person:
    """A placeholder member of the board, known there by `nickname`."""
    person = Person(username=placeholder_username(s, nickname), kind="placeholder", tz=tz)
    s.add(person)
    s.flush()
    s.add(Membership(board_id=board.id, person_id=person.id, nickname=nickname))
    return person


def placeholders(s: Session, board: Board) -> list[tuple[Person, Membership]]:
    return list(s.execute(
        select(Person, Membership).join(Membership, Membership.person_id == Person.id)
        .where(Membership.board_id == board.id, Person.kind == "placeholder")
        .order_by(Membership.nickname)).all())


def claim(s: Session, board: Board, claimer: Person, username: str) -> int:
    """Makes the placeholder `username` on `board` the claimer. Where both filed the same
    puzzle, the claimer's own result stays. Returns how many results moved."""
    if claimer.kind == "placeholder":
        fail(400, "placeholders can't claim")
    if claimer.id in board.settings.get("claimed", {}).values():
        fail(409, "you've already claimed a seat on this board. one each.")
    seat = s.scalar(select(Person).where(Person.username == username, Person.kind == "placeholder"))
    seat_m = seat and s.get(Membership, (board.id, seat.id))
    if not seat_m:
        fail(404, "no such placeholder on this board")

    have = set(s.execute(select(Result.game_id, Result.puzzle_key)
                         .where(Result.person_id == claimer.id)).all())
    moved = 0
    for r in s.scalars(select(Result).where(Result.person_id == seat.id)).all():
        if (r.game_id, r.puzzle_key) in have:
            s.delete(r)
        else:
            r.person_id, moved = claimer.id, moved + 1
    for model in (Paste, GameRequest):
        s.execute(update(model).where(model.person_id == seat.id).values(person_id=claimer.id))

    # every board the placeholder sat on (an import makes one, but don't assume)
    for m in s.scalars(select(Membership).where(Membership.person_id == seat.id)).all():
        # remember whose chat name this was, so a later import files their new messages to them
        b = s.get(Board, m.board_id)
        b.settings = {**b.settings, "claimed": {**b.settings.get("claimed", {}), m.nickname: claimer.id}}
        own = s.get(Membership, (m.board_id, claimer.id))
        if own is None:
            s.add(Membership(board_id=m.board_id, person_id=claimer.id, nickname=m.nickname,
                             joined_at=m.joined_at))
        if own is not None and own.left_at is not None:
            own.left_at = None
        s.flush()
        for game in s.scalars(select(Agenda.game_id).where(
                Agenda.board_id == m.board_id, Agenda.person_id == seat.id)).all():
            if s.get(Agenda, (m.board_id, claimer.id, game)) is None:
                s.add(Agenda(board_id=m.board_id, person_id=claimer.id, game_id=game))
        s.delete(m)  # its agenda rows go with the person, by cascade
    # the chat's chair doesn't come with the seat: anyone holding a forwarded invite could
    # claim it. The chair goes to the longest-serving person already here, else the claimer.
    for b in s.scalars(select(Board).where(Board.chair_id == seat.id)).all():
        heir = s.scalar(select(Membership).join(Person, Person.id == Membership.person_id).where(
            Membership.board_id == b.id, Membership.left_at.is_(None), Person.kind != "placeholder",
            Membership.person_id.not_in([claimer.id, seat.id])).order_by(Membership.joined_at))
        heir = heir or s.get(Membership, (b.id, claimer.id))
        b.chair_id, heir.role = heir.person_id, "chair"
    memos.move(s, seat.id, claimer.id)
    s.flush()
    s.delete(seat)
    s.flush()
    return moved


def merge_guest(s: Session, guest: Person, account: Person) -> dict[str, int]:
    """A guest signing in to a google account that already exists: the guest seat folds
    into the account and is deleted. It's the same person, proven by signing in on the
    guest's own device, so unlike a claim everything comes along: results (where both
    filed the same puzzle, the account's stays, as in a claim), boards with their agendas
    and nicknames, a chair, skips, dismissed memos, the memos about them, and the guest's
    tokens, so the guest's other devices land in the account too. Returns what moved."""
    if guest.kind != "guest" or account.kind != "account" or guest.id == account.id:
        fail(400, "only a guest seat folds into an account")
    have = set(s.execute(select(Result.game_id, Result.puzzle_key).where(Result.person_id == account.id)).all())
    moved = 0
    for r in s.scalars(select(Result).where(Result.person_id == guest.id)).all():
        if (r.game_id, r.puzzle_key) in have:
            s.delete(r)
        else:
            r.person_id, moved = account.id, moved + 1
    for model, col in ((Paste, Paste.person_id), (GameRequest, GameRequest.person_id), (AuthToken, AuthToken.person_id),
                       (Feedback, Feedback.person_id),
                       (Invite, Invite.created_by), (BoardGame, BoardGame.added_by)):
        s.execute(update(model).where(col == guest.id).values({col.key: account.id}))
    for x in s.scalars(select(Skip).where(Skip.person_id == guest.id)).all():
        if s.get(Skip, (account.id, x.game_id, x.day)) is None:
            s.add(Skip(person_id=account.id, game_id=x.game_id, day=x.day, skipped_at=x.skipped_at))
    for x in s.scalars(select(MemoDismissal).where(MemoDismissal.person_id == guest.id)).all():
        if s.get(MemoDismissal, (account.id, x.memo_id)) is None:
            s.add(MemoDismissal(person_id=account.id, memo_id=x.memo_id, dismissed_at=x.dismissed_at))
    s.flush()

    boards = 0
    for m in s.scalars(select(Membership).where(Membership.person_id == guest.id)).all():
        b = s.get(Board, m.board_id)
        own = s.get(Membership, (b.id, account.id))
        if own is None:  # a board only the guest was on: the account takes the seat as it was
            s.add(Membership(board_id=b.id, person_id=account.id, nickname=m.nickname, role=m.role,
                             joined_at=m.joined_at, left_at=m.left_at))
            boards += 1
        else:  # both were on it: the account's seat stays, and keeps the guest's standing
            own.joined_at = min(own.joined_at, m.joined_at)
            if own.left_at is not None and m.left_at is None:
                own.left_at = None
            if m.role == "chair":
                own.role = "chair"
        s.flush()
        if m.left_at is None:
            for game in s.scalars(select(Agenda.game_id).where(Agenda.board_id == b.id, Agenda.person_id == guest.id)).all():
                if s.get(Agenda, (b.id, account.id, game)) is None:
                    s.add(Agenda(board_id=b.id, person_id=account.id, game_id=game))
        if b.chair_id == guest.id:
            b.chair_id = account.id
        claimed = b.settings.get("claimed", {})
        if guest.id in claimed.values():  # a chat name the guest claimed is the account's now
            b.settings = {**b.settings, "claimed": {n: account.id if p == guest.id else p for n, p in claimed.items()}}
        s.delete(m)  # its agenda rows go with it, by cascade
    memos.move(s, guest.id, account.id)
    s.flush()
    s.delete(guest)
    s.flush()
    return {"results": moved, "boards": boards}


def _copy(row, **changes):
    """A new row of the same model with the same columns, apart from its id and `changes`."""
    cols = {c.key: getattr(row, c.key) for c in row.__table__.columns if c.key != "id"}
    return type(row)(**{**cols, **changes})


def unclaim(s: Session, board: Board, person: Person) -> list[Person]:
    """Undoes `claim` on `board` for someone leaving it: each chat name they claimed there
    becomes a placeholder seat again, with the history the import brought (copied, so the
    leaver keeps theirs elsewhere) and their agenda on the board. Results they filed
    themselves stay theirs. Returns the new placeholders."""
    claimed = board.settings.get("claimed", {})
    names = [n for n, pid in claimed.items() if pid == person.id]
    if not names:
        return []
    own = s.get(Membership, (board.id, person.id))
    imported = {p.id: p for p in s.scalars(select(Paste).where(
        Paste.person_id == person.id, Paste.source == "import")).all()}
    seats = []
    for i, name in enumerate(names):
        seat = Person(username=placeholder_username(s, name), kind="placeholder", tz=person.tz)
        s.add(seat)
        s.flush()
        s.add(Membership(board_id=board.id, person_id=seat.id, nickname=name,
                         **({"joined_at": own.joined_at} if own else {})))
        s.flush()
        for game in s.scalars(select(Agenda.game_id).where(
                Agenda.board_id == board.id, Agenda.person_id == person.id)).all():
            s.add(Agenda(board_id=board.id, person_id=seat.id, game_id=game))
        if i == 0:  # an import's pastes don't say whose chat name they were under; the first gets them
            ids = {}
            for pid, paste in imported.items():
                copy = _copy(paste, person_id=seat.id)
                s.add(copy)
                s.flush()
                ids[pid] = copy.id
            for r in s.scalars(select(Result).where(Result.person_id == person.id)).all():
                if r.paste_ids and all(p in ids for p in r.paste_ids):
                    s.add(_copy(r, person_id=seat.id, paste_ids=[ids[p] for p in r.paste_ids]))
        seats.append(seat)
    board.settings = {**board.settings, "claimed": {n: p for n, p in claimed.items() if n not in names}}
    s.flush()
    return seats
