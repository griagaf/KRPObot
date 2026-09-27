import sqlite3
from dataclasses import dataclass

SCHEMA = """
CREATE TABLE IF NOT EXISTS people (
    github_login TEXT PRIMARY KEY COLLATE NOCASE,
    tg_id INTEGER NOT NULL UNIQUE,
    tg_name TEXT NOT NULL,
    tg_username TEXT
);
"""
COLUMNS = "github_login, tg_id, tg_name, tg_username"


@dataclass(frozen=True)
class Person:
    github_login: str
    tg_id: int
    tg_name: str
    tg_username: str | None = None  # без @; не у всех в Telegram он есть


class PeopleStore:
    """Кто есть кто в GitHub и Telegram. Логины GitHub сравниваются без учёта регистра, как в самом GitHub."""

    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db
        self._db.executescript(SCHEMA)
        columns = {row[1] for row in self._db.execute("PRAGMA table_info(people)")}
        if "tg_username" not in columns:  # база прежней версии
            with self._db:
                self._db.execute("ALTER TABLE people ADD COLUMN tg_username TEXT")

    def find(self, github_login: str) -> Person | None:
        row = self._db.execute(f"SELECT {COLUMNS} FROM people WHERE github_login = ?", (github_login,)).fetchone()
        return Person(*row) if row else None

    def find_by_telegram(self, tg_id: int) -> Person | None:
        row = self._db.execute(f"SELECT {COLUMNS} FROM people WHERE tg_id = ?", (tg_id,)).fetchone()
        return Person(*row) if row else None

    def all(self) -> list[Person]:
        rows = self._db.execute(f"SELECT {COLUMNS} FROM people ORDER BY github_login COLLATE NOCASE")
        return [Person(*row) for row in rows]

    def save(self, person: Person) -> None:
        """Один аккаунт Telegram — один логин: прежняя связка этого аккаунта заменяется."""
        with self._db:
            self._db.execute("DELETE FROM people WHERE tg_id = ?", (person.tg_id,))
            self._db.execute(
                f"INSERT OR REPLACE INTO people ({COLUMNS}) VALUES (?, ?, ?, ?)",
                (person.github_login, person.tg_id, person.tg_name, person.tg_username),
            )

    def remove(self, tg_id: int) -> Person | None:
        person = self.find_by_telegram(tg_id)
        if person is not None:
            with self._db:
                self._db.execute("DELETE FROM people WHERE tg_id = ?", (tg_id,))
        return person
