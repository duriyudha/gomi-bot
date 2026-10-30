"""Settings from environment variables. Secrets are never written in code."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    channel_secret: str
    channel_access_token: str
    db_path: str
    schedule_path: str

    @classmethod
    def from_env(cls) -> Settings:
        missing = [k for k in ("LINE_CHANNEL_SECRET", "LINE_CHANNEL_ACCESS_TOKEN") if not os.environ.get(k)]
        if missing:
            raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")
        return cls(
            channel_secret=os.environ["LINE_CHANNEL_SECRET"],
            channel_access_token=os.environ["LINE_CHANNEL_ACCESS_TOKEN"],
            db_path=os.environ.get("DB_PATH", "data/gomi.db"),
            schedule_path=os.environ.get("SCHEDULE_PATH", "schedule.yml"),
        )
