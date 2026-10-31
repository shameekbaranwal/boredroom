"""Rate limits, kept in Postgres so every gunicorn worker sees the same counts and a
restart doesn't reset them. Callers are keyed by IP (an IPv6 /64 counts as one), or by
person for signed-in work."""
from __future__ import annotations

import ipaddress
import random
from datetime import timedelta

from flask import request
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .errors import fail
from .models import ThrottleHit, utcnow


def caller() -> str:
    """The client's address. Only cloudflared can reach the app (its ports are bound to
    localhost), so Cloudflare's header can be trusted."""
    raw = request.headers.get("CF-Connecting-IP") or request.remote_addr or "?"
    try:
        ip = ipaddress.ip_address(raw)
    except ValueError:
        return raw[:45]
    if ip.version == 6:
        return str(ipaddress.ip_network(f"{ip}/64", strict=False))
    return str(ip)


def count(s: Session, key: str, window: int) -> int:
    since = utcnow() - timedelta(seconds=window)
    return s.scalar(select(func.count()).select_from(ThrottleHit).where(
        ThrottleHit.key == key, ThrottleHit.at > since)) or 0


def note(s: Session, *keys: str) -> None:
    """Counts one hit against each key, committed now so it sticks even if the request fails."""
    for k in keys:
        s.add(ThrottleHit(key=k[:120]))
    if random.random() < 0.01:  # now and then, forget hits older than a day
        s.execute(delete(ThrottleHit).where(ThrottleHit.at < utcnow() - timedelta(days=1)))
    s.commit()


def limit(s: Session, key: str, most: int, window: int, message: str) -> None:
    """429 once `key` has `most` hits in the last `window` seconds; otherwise counts this one."""
    if count(s, key, window) >= most:
        fail(429, message)
    note(s, key)
