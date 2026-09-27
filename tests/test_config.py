import pytest

from bot.config import ConfigError, Settings


@pytest.fixture
def env(monkeypatch, tmp_path):
    """Окружение без .env разработчика: из папки теста его не найти."""
    monkeypatch.chdir(tmp_path)
    for name in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "TELEGRAM_THREAD_ID", "GITHUB_TOKEN", "DB_PATH"):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def test_starts_without_chat_id_to_answer_chatid(env):
    env.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    env.setenv("GITHUB_TOKEN", "ghp")
    assert Settings.from_env().chat_id is None


def test_watching_needs_github_token(env):
    env.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    with pytest.raises(ConfigError, match="GITHUB_TOKEN"):
        Settings.from_env()
    assert Settings.from_env(watching=False).github_token == ""


def test_empty_db_path_falls_back_to_file(env):
    env.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    env.setenv("DB_PATH", "")
    assert Settings.from_env(watching=False).db_path == "bot.sqlite3"
