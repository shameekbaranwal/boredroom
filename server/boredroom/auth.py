"""Bearer tokens, one per seat. Guests get one from POST /api/v1/guests; Google sign-in
will mint them the same way once the OAuth client exists (docs/SERVER.md choice 2)."""
from __future__ import annotations

import hashlib
import re
import secrets
from functools import wraps
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import g, request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .errors import fail
from .models import AuthToken, Person, utcnow

USERNAME = re.compile(r"^[a-z0-9][a-z0-9_.-]{1,29}$")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_token(s: Session, person: Person, device: str | None = None) -> str:
    token = secrets.token_urlsafe(32)
    s.add(AuthToken(person_id=person.id, token_hash=hash_token(token), device=device))
    return token


def valid_tz(tz: str) -> bool:
    try:
        ZoneInfo(tz)
        return True
    except (ZoneInfoNotFoundError, ValueError):
        return False


def create_guest(s: Session, username: str | None, tz: str, device: str | None = None) -> tuple[Person, str]:
    if username is None:
        username = f"guest-{secrets.token_hex(3)}"
    username = username.strip().lower()
    if not USERNAME.match(username):
        fail(400, "usernames are 2–30 characters: letters, digits, . _ -")
    if s.scalar(select(Person.id).where(Person.username == username)):
        fail(409, "that username is taken")
    if not valid_tz(tz):
        fail(400, f"unknown timezone {tz}")
    person = Person(username=username, kind="guest", tz=tz)
    s.add(person)
    s.flush()
    return person, issue_token(s, person, device)


def auth_required(view):
    """Sets g.person from the Authorization: Bearer header, or answers 401."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        token = header[7:].strip() if header.lower().startswith("bearer ") else ""
        if not token:
            fail(401, "sign in first")
        row = g.db.scalar(select(AuthToken).where(AuthToken.token_hash == hash_token(token)))
        if row is None:
            fail(401, "that token isn't valid")
        row.last_seen = utcnow()
        g.person = row.person
        return view(*args, **kwargs)
    return wrapped
