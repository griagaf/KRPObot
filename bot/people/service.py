import re

from bot.github import GitHubClient, NotFoundError
from bot.people.store import PeopleStore, Person

GITHUB_LOGIN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})")


class LinkError(Exception):
    pass


class InvalidLoginError(LinkError):
    pass


class UnknownLoginError(LinkError):
    pass


class LoginTakenError(LinkError):
    def __init__(self, owner: Person) -> None:
        super().__init__(owner.github_login)
        self.owner = owner


class PeopleService:
    """Связь GitHub-логинов с аккаунтами Telegram."""

    def __init__(self, store: PeopleStore, github: GitHubClient) -> None:
        self._store = store
        self._github = github

    async def link(self, login: str, tg_id: int, tg_name: str) -> Person:
        login = login.strip().removeprefix("@")
        if not GITHUB_LOGIN.fullmatch(login):
            raise InvalidLoginError(login)
        try:
            login = await self._github.user_login(login)
        except NotFoundError as err:
            raise UnknownLoginError(login) from err

        owner = self._store.find(login)
        if owner is not None and owner.tg_id != tg_id:
            raise LoginTakenError(owner)
        person = Person(login, tg_id, tg_name)
        self._store.save(person)
        return person

    def find_by_telegram(self, tg_id: int) -> Person | None:
        return self._store.find_by_telegram(tg_id)

    def unlink(self, tg_id: int) -> Person | None:
        return self._store.remove(tg_id)

    def all(self) -> list[Person]:
        return self._store.all()
