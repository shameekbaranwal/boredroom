"""Bearer tokens, one per seat. Guests get one from POST /api/v1/guests, accounts from
POST /api/v1/auth/google, which checks a Google ID token (docs/SERVER.md choice 2)."""
from __future__ import annotations

import hashlib
import re
import secrets
import time
from dataclasses import dataclass
from datetime import timedelta
from functools import wraps
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import g, request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .claims import merge_guest
from .errors import fail
from .models import AuthToken, Person, utcnow

USERNAME = re.compile(r"^[a-z0-9][a-z0-9_.-]{1,29}$")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_token(s: Session, person: Person, device: str | None = None, scope: str | None = None) -> str:
    token = secrets.token_urlsafe(32)
    s.add(AuthToken(person_id=person.id, token_hash=hash_token(token), device=device, scope=scope))
    return token


# browsers still report some old zone names; store the current one
TZ_ALIASES = {"Asia/Calcutta": "Asia/Kolkata", "Asia/Saigon": "Asia/Ho_Chi_Minh", "Asia/Katmandu": "Asia/Kathmandu",
              "Asia/Rangoon": "Asia/Yangon", "Europe/Kiev": "Europe/Kyiv", "America/Buenos_Aires": "America/Argentina/Buenos_Aires",
              "US/Eastern": "America/New_York", "US/Central": "America/Chicago", "US/Mountain": "America/Denver",
              "US/Pacific": "America/Los_Angeles"}


def browser_tz(tz: str | None, default: str) -> str:
    """The timezone a browser sent, tidied: aliases become current names, and anything
    unknown becomes the default. Signing in never fails over a timezone; it's editable."""
    tz = TZ_ALIASES.get(tz or "", tz or "")
    return tz if tz and valid_tz(tz) else default


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
    person = Person(username=username, kind="guest", tz=tz)
    s.add(person)
    s.flush()
    return person, issue_token(s, person, device)


def bearer() -> str:
    header = request.headers.get("Authorization", "")
    return header[7:].strip() if header.lower().startswith("bearer ") else ""


TOKEN_IDLE = timedelta(days=180)  # a device unused this long signs in again


def token_row(s: Session, token: str) -> AuthToken | None:
    row = s.scalar(select(AuthToken).where(AuthToken.token_hash == hash_token(token))) if token else None
    if row is not None and row.last_seen < utcnow() - TOKEN_IDLE:
        s.delete(row)
        s.commit()
        return None
    return row


def auth_required(view):
    """Sets g.person from the Authorization: Bearer header, or answers 401."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        token = bearer()
        if not token:
            fail(401, "sign in first")
        row = token_row(g.db, token)
        if row is None:
            fail(401, "that token isn't valid")
        if row.scope is not None:  # a shortcut key only files results, at POST /shortcut
            fail(403, "that key only files results")
        row.last_seen = utcnow()
        g.person, g.token = row.person, row
        return view(*args, **kwargs)
    return wrapped


# -- google ----------------------------------------------------------------------

@dataclass(frozen=True)
class GoogleId:
    sub: str
    email: str
    name: str | None


class _CertCache:
    """Google's signing certs, fetched at most hourly (with a 5 s timeout) instead of on
    every sign-in attempt, so junk credentials don't each cost a request to Google."""
    def __init__(self) -> None:
        from google.auth.transport import requests as google_requests
        self._inner, self._kept = google_requests.Request(), {}

    def __call__(self, url, method="GET", **kw):
        kw.setdefault("timeout", 5)
        if method != "GET":
            return self._inner(url, method=method, **kw)
        hit = self._kept.get(url)
        if hit and hit[0] > time.monotonic():
            return hit[1]
        resp = self._inner(url, method=method, **kw)
        if resp.status == 200:
            self._kept[url] = (time.monotonic() + 3600, resp)
        return resp


_certs: _CertCache | None = None


def verify_google(credential: str, client_id: str) -> GoogleId:
    """Checks a Google ID token's signature, audience, issuer and expiry."""
    global _certs
    from google.auth.exceptions import GoogleAuthError
    from google.oauth2 import id_token

    if credential.count(".") != 2:  # not even shaped like a JWT
        fail(400, "that isn't a google credential")
    _certs = _certs or _CertCache()
    try:
        claims = id_token.verify_oauth2_token(credential, _certs, client_id)
    except (ValueError, GoogleAuthError):  # bad signature, audience, issuer, expiry, or no certs
        fail(401, "google didn't vouch for that sign-in; try again")
    if not claims.get("email_verified"):
        fail(401, "that google account's email isn't verified")
    return GoogleId(claims["sub"], claims["email"].lower(), claims.get("name"))


def username_for(s: Session, email: str) -> str:
    """The email's local part, cleaned up, with a number added if it's taken."""
    base = re.sub(r"[^a-z0-9_.-]", "", email.split("@")[0].lower()).lstrip("._-")[:26]
    if len(base) < 2:
        base = "member"
    name, n = base, 1
    while s.scalar(select(Person.id).where(Person.username == name)):
        n += 1
        name = f"{base}{n}"
    return name


def sign_in_google(s: Session, who: GoogleId, tz: str, seat: Person | None,
                   device: str | None = None) -> tuple[Person, str, bool, dict[str, int] | None]:
    """Finds the account for this google id, or makes one: from the guest seat if one is
    signed in (keeping its history), else fresh. A guest signing in to an account that
    already exists folds into it (claims.merge_guest). Returns (person, token, created,
    what the merge moved, if there was one)."""
    person = s.scalar(select(Person).where(Person.google_sub == who.sub))
    created, merged = False, None
    if person is not None and seat is not None and seat.kind == "guest" and seat.id != person.id:
        merged = merge_guest(s, seat, person)
    if person is None:
        if seat is not None and seat.kind == "guest":
            person = seat
        else:
            person = Person(username=username_for(s, who.email), tz=tz)
            s.add(person)
            created = True
        person.kind, person.google_sub = "account", who.sub
    person.email = who.email
    s.flush()
    return person, issue_token(s, person, device), created, merged
