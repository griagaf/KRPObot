import json
import sqlite3
from collections.abc import Iterable
from datetime import datetime

from bot.domain.models import PullRequest

SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_events (key TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS pull_requests (
    id INTEGER PRIMARY KEY,
    updated_at TEXT NOT NULL,
    reviewers TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS watched_repos (repo TEXT PRIMARY KEY, since TEXT NOT NULL);
"""


class WatchState:
    """Что бот уже видел в репозиториях: защищает от повторов, в том числе после перезапуска."""

    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db
        self._db.executescript(SCHEMA)

    def is_seen(self, key: str) -> bool:
        return self._db.execute("SELECT 1 FROM seen_events WHERE key = ?", (key,)).fetchone() is not None

    def mark_seen(self, keys: Iterable[str]) -> None:
        with self._db:
            self._db.executemany("INSERT OR IGNORE INTO seen_events (key) VALUES (?)", ((k,) for k in keys))

    def last_update(self, pr_id: int) -> datetime | None:
        row = self._db.execute("SELECT updated_at FROM pull_requests WHERE id = ?", (pr_id,)).fetchone()
        return datetime.fromisoformat(row[0]) if row else None

    def known_reviewers(self, pr_id: int) -> tuple[str, ...] | None:
        row = self._db.execute("SELECT reviewers FROM pull_requests WHERE id = ?", (pr_id,)).fetchone()
        return tuple(json.loads(row[0])) if row else None

    def remember_pulls(self, pulls: Iterable[PullRequest]) -> None:
        with self._db:
            self._db.executemany(
                "INSERT OR REPLACE INTO pull_requests (id, updated_at, reviewers) VALUES (?, ?, ?)",
                ((pr.id, pr.updated_at.isoformat(), json.dumps(pr.requested_reviewers)) for pr in pulls),
            )

    def watching_since(self, repo: str) -> datetime | None:
        row = self._db.execute("SELECT since FROM watched_repos WHERE repo = ?", (repo,)).fetchone()
        return datetime.fromisoformat(row[0]) if row else None

    def start_watching(self, repo: str, since: datetime) -> None:
        with self._db:
            self._db.execute(
                "INSERT OR REPLACE INTO watched_repos (repo, since) VALUES (?, ?)", (repo, since.isoformat())
            )
