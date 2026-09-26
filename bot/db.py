import sqlite3


def connect(path: str) -> sqlite3.Connection:
    """Одно соединение на процесс: бот однопоточный, запросы короткие. Схему создают хранилища."""
    return sqlite3.connect(path)
