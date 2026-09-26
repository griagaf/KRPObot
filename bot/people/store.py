import sqlite3
from dataclasses import dataclass

SCHEMA = """
CREATE TABLE IF NOT EXISTS people (
    github_login TEXT PRIMARY KEY COLLATE NOCASE,
    tg_id INTEGER NOT NULL UNIQUE,
    tg_name TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class Person:
    github_login: str
    tg_id: int
    tg_name: str


class PeopleStore:
    """Кто есть кто в GitHub и Telegram. Логины GitHub сравниваются без учёта регистра, как в самом GitHub."""

    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db
        self._db.executescript(SCHEMA)

    def find(self, github_login: str) -> Person | None:
        row = self._db.execute(
            "SELECT github_login, tg_id, tg_name FROM people WHERE github_login = ?", (github_login,)
        ).fetchone()
        return Person(*row) if row else None

    def all(self) -> list[Person]:
        rows = self._db.execute("SELECT github_login, tg_id, tg_name FROM people ORDER BY github_login COLLATE NOCASE")
        return [Person(*row) for row in rows]

    def save(self, person: Person) -> None:
        """Один аккаунт Telegram — один логин: прежняя связка этого аккаунта заменяется."""
        with self._db:
            self._db.execute("DELETE FROM people WHERE tg_id = ?", (person.tg_id,))
            self._db.execute(
                "INSERT OR REPLACE INTO people (github_login, tg_id, tg_name) VALUES (?, ?, ?)",
                (person.github_login, person.tg_id, person.tg_name),
            )

    def remove(self, tg_id: int) -> Person | None:
        row = self._db.execute("SELECT github_login, tg_id, tg_name FROM people WHERE tg_id = ?", (tg_id,)).fetchone()
        if row is None:
            return None
        with self._db:
            self._db.execute("DELETE FROM people WHERE tg_id = ?", (tg_id,))
        return Person(*row)
