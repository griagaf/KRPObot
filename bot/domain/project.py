"""Чем один проект отличается от другого. Всё остальное в боте общее, так что для нового проекта
достаточно другого Project: его собирает config из переменных окружения."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from bot.domain.models import ReviewRequests


@dataclass(frozen=True)
class Reviewers:
    logins: tuple[str, ...]
    teams_without_members: tuple[str, ...]  # состав не задан, отметить некого


@dataclass(frozen=True)
class Project:
    org: str
    # dejaview-backend -> backend: общий префикс репозиториев в сообщениях только мешает
    repo_prefix: str = ""
    # команда GitHub -> логины участников. GitHub отдаёт состав команды только токену с правами на
    # организацию, поэтому его задают в настройках, иначе запрос ревью у команды никого не отметит
    teams: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    # в какой статус перевести задачу трекера после слияния PR
    task_done_status: str = "Resolved"

    def team_members(self, team: str) -> tuple[str, ...]:
        return self.teams.get(team.lower(), ())

    def reviewers(self, requests: ReviewRequests, code_owners: ReviewRequests, author: str) -> Reviewers:
        """Кого отметить, когда просят ревью. Людей из запроса — всегда. Вместо команды, которая по
        CODEOWNERS владеет изменённым кодом, — персональных владельцев изменённых файлов, например
        ментора направления: команда при нём запасная. Если таких нет или это сам автор, то всю команду."""
        owners = [login for login in code_owners.users if login.lower() != author.lower()]
        owner_teams = {team.lower() for team in code_owners.teams}
        logins = list(requests.users)
        without_members = []
        for team in requests.teams:
            if owners and team.lower() in owner_teams:
                logins += owners
            elif members := self.team_members(team):
                logins += members
            else:
                without_members.append(team)
        return Reviewers(_unique_except(logins, author), tuple(without_members))

    def team_url(self, team: str) -> str:
        return f"https://github.com/orgs/{self.org}/teams/{team}"

    def short_repo(self, name: str) -> str:
        return name.removeprefix(self.repo_prefix)


def _unique_except(logins: Iterable[str], excluded: str) -> tuple[str, ...]:
    """Без повторов и без excluded; логины GitHub не зависят от регистра."""
    unique: dict[str, str] = {}
    for login in logins:
        if login.lower() != excluded.lower():
            unique.setdefault(login.lower(), login)
    return tuple(unique.values())
