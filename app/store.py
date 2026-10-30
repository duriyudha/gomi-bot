"""SQLite storage: subscribers and the monthly push count."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._execute(
            "CREATE TABLE IF NOT EXISTS subscribers ("
            " user_id TEXT PRIMARY KEY,"
            " created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        self._execute(
            "CREATE TABLE IF NOT EXISTS push_log ("
            " month TEXT PRIMARY KEY,"  # e.g. "2026-10"
            " count INTEGER NOT NULL)"
        )

    def _execute(self, sql: str, params: tuple = ()) -> list[tuple]:
        # One short connection per call, so the webhook and the
        # scheduler thread can both use the store safely.
        with closing(sqlite3.connect(self.path)) as conn, conn:
            return conn.execute(sql, params).fetchall()

    # --- subscribers ---

    def add_subscriber(self, user_id: str) -> None:
        self._execute("INSERT OR IGNORE INTO subscribers (user_id) VALUES (?)", (user_id,))

    def remove_subscriber(self, user_id: str) -> None:
        self._execute("DELETE FROM subscribers WHERE user_id = ?", (user_id,))

    def subscribers(self) -> list[str]:
        rows = self._execute("SELECT user_id FROM subscribers ORDER BY created_at")
        return [r[0] for r in rows]

    # --- push count ---

    def push_count(self, month: str) -> int:
        rows = self._execute("SELECT count FROM push_log WHERE month = ?", (month,))
        return rows[0][0] if rows else 0

    def add_push(self, month: str) -> int:
        """Add 1 to this month's push count and return the new count."""
        self._execute(
            "INSERT INTO push_log (month, count) VALUES (?, 1)"
            " ON CONFLICT(month) DO UPDATE SET count = count + 1",
            (month,),
        )
        return self.push_count(month)
