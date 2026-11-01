"""The data model. See docs/SERVER.md part 3.

Games aren't a table: the library is the parser registry, and boards refer to games
by id ("krillion").
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import (
    ARRAY, Boolean, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, String, Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Person(Base):
    __tablename__ = "person"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(40), unique=True)
    # guest: a real account with no sign-in yet; account: signed in with google;
    # placeholder: a sender from an imported chat, waiting to be claimed
    kind: Mapped[str] = mapped_column(String(12), default="guest")
    tz: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True)
    email: Mapped[str | None] = mapped_column(String(320))
    agenda_sort: Mapped[str | None] = mapped_column(String(20))  # "resets:first"; none is the usual
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    memberships: Mapped[list["Membership"]] = relationship(back_populates="person")


class AuthToken(Base):
    """A seat's bearer token. Only its hash is stored."""
    __tablename__ = "auth_token"

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("person.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    device: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    person: Mapped[Person] = relationship()


class Board(Base):
    __tablename__ = "board"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60))
    slug: Mapped[str] = mapped_column(String(60), unique=True)
    chair_id: Mapped[int] = mapped_column(ForeignKey("person.id"))
    # late_filing (bool), join ("link" | "approval")
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    memberships: Mapped[list["Membership"]] = relationship(back_populates="board")
    library: Mapped[list["BoardGame"]] = relationship(back_populates="board", cascade="all, delete-orphan")


class Invite(Base):
    """A way onto a board: three words (see invites.py). Boards can have several."""
    __tablename__ = "invite"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True)
    board_id: Mapped[int] = mapped_column(ForeignKey("board.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("person.id", ondelete="SET NULL"))
    legacy: Mapped[bool] = mapped_column(Boolean, default=False)  # an old random code, kept working
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    board: Mapped[Board] = relationship()


class Membership(Base):
    __tablename__ = "membership"

    board_id: Mapped[int] = mapped_column(ForeignKey("board.id", ondelete="CASCADE"), primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("person.id", ondelete="CASCADE"), primary_key=True)
    nickname: Mapped[str] = mapped_column(String(40))
    role: Mapped[str] = mapped_column(String(12), default="member")  # chair | member
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    board: Mapped[Board] = relationship(back_populates="memberships")
    person: Mapped[Person] = relationship(back_populates="memberships")


class BoardGame(Base):
    """A game in a board's library, with the board's rule overrides."""
    __tablename__ = "board_game"

    board_id: Mapped[int] = mapped_column(ForeignKey("board.id", ondelete="CASCADE"), primary_key=True)
    game_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    added_by: Mapped[int | None] = mapped_column(ForeignKey("person.id", ondelete="SET NULL"))
    # ranked (bool), ranker (list of metric names), late_filing (bool)
    rules: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    board: Mapped[Board] = relationship(back_populates="library")


class Agenda(Base):
    """The games a member plays on a board."""
    __tablename__ = "agenda"
    __table_args__ = (
        ForeignKeyConstraint(["board_id", "game_id"], ["board_game.board_id", "board_game.game_id"],
                             ondelete="CASCADE"),
    )

    board_id: Mapped[int] = mapped_column(ForeignKey("board.id", ondelete="CASCADE"), primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("person.id", ondelete="CASCADE"), primary_key=True)
    game_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Paste(Base):
    """Everything anyone pasted, kept so results can be re-parsed later."""
    __tablename__ = "paste"

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("person.id", ondelete="CASCADE"), index=True)
    raw: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(12), default="paste")  # paste | share | import
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Result(Base):
    __tablename__ = "result"
    __table_args__ = (UniqueConstraint("person_id", "game_id", "puzzle_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("person.id", ondelete="CASCADE"), index=True)
    game_id: Mapped[str] = mapped_column(String(40))
    puzzle_key: Mapped[str] = mapped_column(String(200))
    puzzle_day: Mapped[date | None] = mapped_column(Date, index=True)
    outcome: Mapped[str] = mapped_column(String(10))
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    fields: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    highlights: Mapped[list[str]] = mapped_column(ARRAY(String(40)), default=list)
    extras: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    comment: Mapped[str] = mapped_column(Text, default="")
    raw: Mapped[str] = mapped_column(Text)  # the text "send to soup" forwards
    confidence: Mapped[str] = mapped_column(String(10))
    warnings: Mapped[list[str]] = mapped_column(JSONB, default=list)
    parser: Mapped[str] = mapped_column(String(40))
    late: Mapped[bool] = mapped_column(Boolean, default=False)
    filed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    amended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paste_ids: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list)


class PuzzleDay(Base):
    """The day a page-pair puzzle (wiki game) belongs to: set by its first filing."""
    __tablename__ = "puzzle_day"

    game_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    puzzle_key: Mapped[str] = mapped_column(String(200), primary_key=True)
    day: Mapped[date] = mapped_column(Date)


class GameRequest(Base):
    """A paste from a game we have no parser for: the queue of parsers to write."""
    __tablename__ = "game_request"

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int | None] = mapped_column(ForeignKey("person.id", ondelete="SET NULL"))
    name: Mapped[str | None] = mapped_column(String(100))
    link: Mapped[str | None] = mapped_column(String(200))
    raw: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ThrottleHit(Base):
    """One request counted against a rate limit (see throttle.py)."""
    __tablename__ = "throttle_hit"
    __table_args__ = (Index("ix_throttle_hit_key_at", "key", "at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(120))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Memo(Base):
    """A memo from the chair, stored the first time it's seen (see memos.py). Its facts
    stay fixed; its text is rendered when read."""
    __tablename__ = "memo"
    __table_args__ = (UniqueConstraint("board_id", "key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    board_id: Mapped[int] = mapped_column(ForeignKey("board.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(200))  # "record:maptap:2026-10-31"
    kind: Mapped[str] = mapped_column(String(20))
    day: Mapped[date] = mapped_column(Date, index=True)  # the meeting that reports it
    subjects: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list)  # who it's about
    game_id: Mapped[str | None] = mapped_column(String(40))
    result_id: Mapped[int | None] = mapped_column(ForeignKey("result.id", ondelete="CASCADE"))
    facts: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    interest: Mapped[int] = mapped_column(Integer, default=50)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MemoDismissal(Base):
    """A memo someone waved off the agenda. It stays in the meeting."""
    __tablename__ = "memo_dismissal"

    person_id: Mapped[int] = mapped_column(ForeignKey("person.id", ondelete="CASCADE"), primary_key=True)
    memo_id: Mapped[int] = mapped_column(ForeignKey("memo.id", ondelete="CASCADE"), primary_key=True)
    dismissed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
