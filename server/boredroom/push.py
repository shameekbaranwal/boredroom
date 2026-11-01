"""Web push: sending one notification to one device, and the devices themselves.

A push goes to the browser's push service (FCM for Chrome, Apple's for iPhones,
Mozilla's for Firefox), signed with this server's VAPID key, encrypted for the device.
Payloads carry game names, counts and your own tenure, never results."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Config
from .errors import fail
from .models import Person, PushSubscription, utcnow

GONE = 3  # failures in a row before a device is dropped; a 404 or 410 drops it at once


@dataclass
class Push:
    title: str
    body: str
    url: str = "/"
    tag: str = "boredroom"

    def json(self) -> str:
        return json.dumps({"title": self.title, "body": self.body, "url": self.url, "tag": self.tag})


# a sender takes (subscription, push, config) and returns the push service's status code
Sender = Callable[[PushSubscription, Push, Config], int]


def webpush_sender(sub: PushSubscription, push: Push, cfg: Config) -> int:
    from pywebpush import WebPushException, webpush
    try:
        r = webpush(subscription_info={"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}},
                    data=push.json(), vapid_private_key=cfg.vapid_private_key,
                    vapid_claims={"sub": f"mailto:{cfg.contact_email or 'nobody@example.com'}"},
                    ttl=3600, timeout=10, headers={"Urgency": "high"})
        return r.status_code
    except WebPushException as e:
        return e.response.status_code if e.response is not None else 0
    except Exception:  # the push service didn't answer
        return 0


def deliver(s: Session, person_id: int, push: Push, cfg: Config, send: Sender) -> int:
    """Sends to every device a person has; returns how many took it. Devices the push
    service says are gone are dropped, and so are ones that keep failing."""
    ok = 0
    for sub in s.scalars(select(PushSubscription).where(PushSubscription.person_id == person_id)):
        status = send(sub, push, cfg)
        if 200 <= status < 300:
            ok += 1
            sub.failures, sub.last_ok_at = 0, utcnow()
        elif status in (404, 410):
            s.delete(sub)
        else:
            sub.failures += 1
            if sub.failures >= GONE:
                s.delete(sub)
    s.commit()
    return ok


def device_name(ua: str) -> str:
    """'android · chrome', 'iphone · app': enough to tell your devices apart."""
    ua = ua.lower()
    os_ = "iphone" if "iphone" in ua else "ipad" if "ipad" in ua else "android" if "android" in ua \
        else "mac" if "mac os" in ua else "windows" if "windows" in ua else "linux" if "linux" in ua else "a device"
    br = "firefox" if "firefox" in ua else "edge" if "edg/" in ua else "samsung" if "samsungbrowser" in ua \
        else "chrome" if "chrome" in ua or "crios" in ua else "safari" if "safari" in ua else ""
    if os_ in ("iphone", "ipad") and "safari" not in ua:
        br = "app"  # the installed app's web view says no browser at all
    return f"{os_} · {br}" if br else os_


ENDPOINT = re.compile(r"^https://[a-z0-9.-]+(:\d+)?/\S+$", re.I)


def subscribe(s: Session, person: Person, b: dict[str, Any], ua: str) -> PushSubscription:
    """Saves this device's subscription. The same endpoint again is the same device; one
    that arrives from someone else (a phone that changed hands) moves to them."""
    endpoint, keys = b.get("endpoint"), b.get("keys") or {}
    if not isinstance(endpoint, str) or len(endpoint) > 1000 or not ENDPOINT.match(endpoint):
        fail(400, "that isn't a push subscription")
    p256dh, auth = keys.get("p256dh") if isinstance(keys, dict) else None, keys.get("auth") if isinstance(keys, dict) else None
    if not isinstance(p256dh, str) or not isinstance(auth, str) or len(p256dh) > 200 or len(auth) > 100:
        fail(400, "that subscription has no keys")
    sub = s.scalar(select(PushSubscription).where(PushSubscription.endpoint == endpoint))
    if sub is None:
        sub = PushSubscription(endpoint=endpoint, person_id=person.id, p256dh=p256dh, auth=auth)
        s.add(sub)
    sub.person_id, sub.p256dh, sub.auth, sub.failures = person.id, p256dh, auth, 0
    sub.device = device_name(ua)
    s.flush()
    return sub


def devices_json(s: Session, person: Person) -> list[dict[str, Any]]:
    return [{"id": d.id, "device": d.device, "endpoint": d.endpoint, "since": d.created_at.isoformat(),
             "last_ok_at": d.last_ok_at.isoformat() if d.last_ok_at else None}
            for d in s.scalars(select(PushSubscription).where(PushSubscription.person_id == person.id)
                               .order_by(PushSubscription.created_at))]
