"""Settings, read from the environment."""
from __future__ import annotations

import os
from dataclasses import dataclass

DEV_DATABASE_URL = "postgresql+psycopg://boredroom:boredroom@127.0.0.1:5433/boredroom"


@dataclass(frozen=True)
class Config:
    database_url: str = os.environ.get("DATABASE_URL", DEV_DATABASE_URL)
    default_tz: str = os.environ.get("BOREDROOM_DEFAULT_TZ", "Asia/Kolkata")
    max_paste_bytes: int = 256 * 1024
