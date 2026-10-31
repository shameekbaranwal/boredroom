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
