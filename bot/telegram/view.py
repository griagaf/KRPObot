from collections.abc import Callable
from typing import Protocol

from bot.domain.project import Project
from bot.people import Person
from bot.telegram.markup import esc, hashtag, link


class PeopleLookup(Protocol):
    def find(self, github_login: str) -> Person | None: ...


class View:
    """Как бот называет в сообщениях людей, команды, репозитории и задачи."""

    def __init__(self, people: PeopleLookup, issue_url: Callable[[int], str], project: Project) -> None:
        self._people = people
        self._issue_url = issue_url
        self.project = project

    def repo(self, name: str) -> str:
        return self.project.short_repo(name)

    def repo_tag(self, name: str) -> str:
        return hashtag(self.repo(name))

    def task(self, task_id: int, text: str | None = None) -> str:
        return link(self._issue_url(task_id), text or f"#{task_id}")

    def is_linked(self, login: str) -> bool:
        return self._people.find(login) is not None

    def name(self, login: str) -> str:
        """Кто сделал действие: имя без упоминания, чтобы не тревожить самого автора."""
        person = self._people.find(login)
        return f"<b>{esc(person.tg_name)}</b>" if person else self.github_profile(login)

    def mention(self, login: str) -> str:
        """Кому нужно отреагировать: упоминание, Telegram пришлёт уведомление."""
        person = self._people.find(login)
        if person is None:
            return self.github_profile(login)
        if person.tg_username:
            # @username уведомляет всегда, а ссылка tg://user — только тех, кто писал боту в личку
            return f"@{esc(person.tg_username)}"
        return f'<a href="tg://user?id={person.tg_id}">{esc(person.tg_name)}</a>'

    def team(self, team: str) -> str:
        return link(self.project.team_url(team), f"👥 {esc(team)}")

    @staticmethod
    def github_profile(login: str) -> str:
        return link(f"https://github.com/{login}", esc(login))
