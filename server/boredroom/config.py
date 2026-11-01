"""Settings, read from the environment."""
from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass

DEV_DATABASE_URL = "postgresql+psycopg://boredroom:boredroom@127.0.0.1:5433/boredroom"
# the built web app (web/dist); in the image it's copied to /app/web
DEV_WEB_DIST = str(Path(__file__).resolve().parents[2] / "web" / "dist")


@dataclass(frozen=True)
class Config:
    database_url: str = os.environ.get("DATABASE_URL", DEV_DATABASE_URL)
    default_tz: str = os.environ.get("BOREDROOM_DEFAULT_TZ", "Asia/Kolkata")
    max_paste_bytes: int = 64 * 1024  # any request body; pastes are capped at 16k characters (api.py)
    # sign-in only needs the client id; the client secret is never read
    google_client_id: str | None = os.environ.get("GOOGLE_OAUTH_CLIENT_ID") or None
    web_dist: str = os.environ.get("BOREDROOM_WEB_DIST", DEV_WEB_DIST)
    # "production", "stage" or "dev"; the app badges anything that isn't production
    environment: str = os.environ.get("BOREDROOM_ENV", "dev")
    # web push (reminders). The public key goes to browsers; the private key never leaves
    # the server. Without both, reminders are off and the app says so.
    vapid_public_key: str | None = os.environ.get("BOREDROOM_VAPID_PUBLIC_KEY") or None
    vapid_private_key: str | None = os.environ.get("BOREDROOM_VAPID_PRIVATE_KEY") or None
    contact_email: str | None = os.environ.get("BOREDROOM_CONTACT_EMAIL") or None
    # the minute-by-minute reminder scheduler; on in the image, off in tests and dev
    scheduler: bool = os.environ.get("BOREDROOM_SCHEDULER", "off") == "on"

    @property
    def push(self) -> bool:
        return bool(self.vapid_public_key and self.vapid_private_key)
