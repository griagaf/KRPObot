import os
from dataclasses import dataclass
from typing import Self
from zoneinfo import ZoneInfo

from dotenv import find_dotenv, load_dotenv

from bot.domain.project import Project

REQUIRED = ("TELEGRAM_BOT_TOKEN", "GITHUB_ORG")
REQUIRED_FOR_WATCHING = ("GITHUB_TOKEN",)
CI_NOTIFY_MODES = ("all", "failures")


class ConfigError(Exception):
    pass


def parse_chat_id(value: str) -> int | str:
    """Числовой id чата (группа, личка) или @username канала."""
    return int(value) if value.lstrip("-").isdigit() else value


def parse_teams(value: str) -> dict[str, tuple[str, ...]]:
    """«maintainers=alice,bob; backend=carol» → {команда: логины}. Команду можно писать как в CODEOWNERS:
    @org/maintainers."""
    teams: dict[str, tuple[str, ...]] = {}
    for entry in filter(None, (part.strip() for part in value.split(";"))):
        team, has_members, logins = entry.partition("=")
        name = team.strip().removeprefix("@").rsplit("/", 1)[-1].lower()
        members = tuple(login.strip().removeprefix("@") for login in logins.split(",") if login.strip())
        if not has_members or not name or not members:
            raise ConfigError(f"GITHUB_TEAMS: не понял «{entry}», нужно команда=логин,логин")
        teams[name] = members
    return teams


@dataclass(frozen=True)
class Settings:
    telegram_token: str
    chat_id: int | str | None  # куда слать уведомления; без него работают только команды
    thread_id: int | None
    github_token: str
    project: Project
    repos: tuple[str, ...]
    poll_interval: int
    notify_build_success: bool
    redmine_url: str
    redmine_api_key: str | None
    db_path: str
    timezone: ZoneInfo

    @classmethod
    def from_env(cls, *, watching: bool = True) -> Self:
        """watching=False — демо-режим: только команды, без наблюдения за репозиториями.
        GitHub тогда опрашивается анонимно, этого хватает на команды."""
        # .env из папки запуска: без usecwd его ищут рядом с кодом, а у установленного пакета это site-packages
        load_dotenv(find_dotenv(usecwd=True))
        required = REQUIRED + REQUIRED_FOR_WATCHING if watching else REQUIRED
        if missing := [name for name in required if not os.getenv(name)]:
            raise ConfigError("Не заданы переменные окружения: " + ", ".join(missing))
        ci_notify = os.getenv("CI_NOTIFY", "all")
        if ci_notify not in CI_NOTIFY_MODES:
            raise ConfigError(f"CI_NOTIFY должен быть одним из: {', '.join(CI_NOTIFY_MODES)}")

        org = os.environ["GITHUB_ORG"]
        # dejaview-nsu -> dejaview-: у репозиториев организации обычно общий префикс
        repo_prefix = os.getenv("REPO_PREFIX")
        project = Project(
            org=org,
            repo_prefix=org.split("-")[0] + "-" if repo_prefix is None else repo_prefix,
            teams=parse_teams(os.getenv("GITHUB_TEAMS", "")),
            task_done_status=os.getenv("TASK_DONE_STATUS") or "Resolved",
        )
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        thread_id = os.getenv("TELEGRAM_THREAD_ID")
        return cls(
            telegram_token=os.environ["TELEGRAM_BOT_TOKEN"],
            chat_id=parse_chat_id(chat_id) if chat_id else None,
            thread_id=int(thread_id) if thread_id else None,
            github_token=os.getenv("GITHUB_TOKEN", ""),
            project=project,
            repos=tuple(r.strip() for r in os.getenv("GITHUB_REPOS", "").split(",") if r.strip()),
            poll_interval=int(os.getenv("POLL_INTERVAL", "60")),
            notify_build_success=ci_notify == "all",
            redmine_url=os.getenv("REDMINE_URL", "https://ai.nsu.ru").rstrip("/"),
            redmine_api_key=os.getenv("REDMINE_API_KEY") or None,
            db_path=os.getenv("DB_PATH") or "bot.sqlite3",  # на "" sqlite молча открыл бы временную базу
            timezone=ZoneInfo(os.getenv("TIMEZONE", "Asia/Novosibirsk")),
        )
