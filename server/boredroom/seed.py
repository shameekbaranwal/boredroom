"""Seat a board's history before its members join: one placeholder member per name, every
share text filed at the time it was posted, agendas from the games each name played.
Members claim their placeholder from the board ("that's me"). Re-running files nothing
twice (repeats are duplicates), and a name someone has claimed files to whoever claimed it.

Turning a particular chat into messages is the caller's business; nothing here knows
where they came from."""
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from boredroom import boards, claims, filing
from boredroom.models import Board, Membership, Person
from boredroom.parser import REGISTRY

Message = tuple[datetime, str, str, str]  # posted at, name on the board, timezone, text


def seed(s: Session, board_name: str, msgs: Iterable[Message], chair: str | None = None) -> Counter:
    """Files `msgs` into the board called `board_name`, creating it on first run with
    `chair` (a name, default the first) holding the chair until claimed. No commit.
    Returns event counts."""
    msgs = list(msgs)
    board = s.scalar(select(Board).where(Board.name == board_name))
    seats: dict[str, Person] = {}
    if board is not None:  # a re-run: the placeholders by nickname, and whoever claimed one
        for p, m in claims.placeholders(s, board):
            seats[m.nickname] = p
        for nick, pid in board.settings.get("claimed", {}).items():
            if (claimer := s.get(Person, pid)) is not None:
                seats[nick] = claimer
    stats: Counter = Counter()
    played: dict[str, set[str]] = defaultdict(set)
    if board is None and msgs:
        nick = chair or msgs[0][1]
        tz = next((t for _, n, t, _ in msgs if n == nick), msgs[0][2])
        first = Person(username=claims.placeholder_username(s, nick), kind="placeholder", tz=tz)
        s.add(first)
        s.flush()
        board = boards.create_board(s, first, board_name)
        s.flush()
        s.get(Membership, (board.id, first.id)).nickname = nick
        seats[nick] = first
    for ts, nick, tz, body in msgs:
        person = seats.get(nick)
        if person is None:
            person = seats[nick] = claims.add_placeholder(s, board, nick, tz)
        f = filing.file_paste(s, person, body, now=ts, source="import")
        for e in f.events:
            stats[e.kind] += 1
            played[nick].add(e.game)
        stats["unknown"] += len(f.unknown)
    for nick, games in played.items():
        for game in sorted(games):
            if not REGISTRY[game].ignore:
                boards.set_agenda(s, board, seats[nick], game, True)
    s.flush()
    stats["members"] = len(seats)
    return stats
