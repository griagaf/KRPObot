from collections.abc import Callable, Iterable
from typing import Protocol

from bot.people import Person
from bot.telegram.markup import esc, hashtag, link


class PeopleLookup(Protocol):
    def find(self, github_login: str) -> Person | None: ...


class View:
    """Как бот называет в сообщениях людей, репозитории и задачи."""

    def __init__(self, people: PeopleLookup, issue_url: Callable[[int], str], org: str) -> None:
        self._people = people
        self._issue_url = issue_url
        # dejaview-backend -> backend: общий префикс организации в сообщениях только мешает
        self._repo_prefix = org.split("-")[0] + "-"

    def repo(self, name: str) -> str:
        return name.removeprefix(self._repo_prefix)

    def repo_tag(self, name: str) -> str:
        return hashtag(self.repo(name))

    def task(self, task_id: int, text: str | None = None) -> str:
        return link(self._issue_url(task_id), text or f"#{task_id}")

    def name(self, login: str) -> str:
        """Кто сделал действие: имя без упоминания, чтобы не тревожить самого автора."""
        person = self._people.find(login)
        return f"<b>{esc(person.tg_name)}</b>" if person else self.github_profile(login)

    def mention(self, login: str) -> str:
        """Кому нужно отреагировать: упоминание, Telegram пришлёт уведомление."""
        person = self._people.find(login)
        if person is None:
            return self.github_profile(login)
        return f'<a href="tg://user?id={person.tg_id}">{esc(person.tg_name)}</a>'

    def mentions(self, logins: Iterable[str]) -> str:
        return ", ".join(self.mention(login) for login in logins)

    @staticmethod
    def github_profile(login: str) -> str:
        return link(f"https://github.com/{login}", esc(login))
