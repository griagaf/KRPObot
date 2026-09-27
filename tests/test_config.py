import pytest

from bot.config import ConfigError, Settings, parse_teams

VARIABLES = (
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "TELEGRAM_THREAD_ID",
    "GITHUB_TOKEN",
    "GITHUB_ORG",
    "GITHUB_TEAMS",
    "REPO_PREFIX",
    "TASK_DONE_STATUS",
    "DB_PATH",
)


@pytest.fixture
def env(monkeypatch, tmp_path):
    """Окружение без .env разработчика: из папки теста его не найти. Заданы только обязательные переменные."""
    monkeypatch.chdir(tmp_path)
    for name in VARIABLES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("GITHUB_ORG", "dejaview-nsu")
    return monkeypatch


def test_starts_without_chat_id_to_answer_chatid(env):
    env.setenv("GITHUB_TOKEN", "ghp")
    assert Settings.from_env().chat_id is None


def test_watching_needs_github_token(env):
    with pytest.raises(ConfigError, match="GITHUB_TOKEN"):
        Settings.from_env()
    assert Settings.from_env(watching=False).github_token == ""


def test_org_has_no_default(env):
    env.delenv("GITHUB_ORG")
    with pytest.raises(ConfigError, match="GITHUB_ORG"):
        Settings.from_env(watching=False)


def test_empty_db_path_falls_back_to_file(env):
    env.setenv("DB_PATH", "")
    assert Settings.from_env(watching=False).db_path == "bot.sqlite3"


def test_project_defaults_come_from_org(env):
    project = Settings.from_env(watching=False).project
    assert (project.org, project.repo_prefix, project.task_done_status) == ("dejaview-nsu", "dejaview-", "Resolved")
    env.setenv("REPO_PREFIX", "")
    assert Settings.from_env(watching=False).project.repo_prefix == ""


def test_teams_accept_codeowners_spelling():
    assert parse_teams("@dejaview-nsu/Maintainers = @alice, bob; backend=carol;") == {
        "maintainers": ("alice", "bob"),
        "backend": ("carol",),
    }
    assert parse_teams("") == {}


@pytest.mark.parametrize("value", ["maintainers", "maintainers=", "=alice"])
def test_bad_teams_are_reported(value):
    with pytest.raises(ConfigError, match="GITHUB_TEAMS"):
        parse_teams(value)
