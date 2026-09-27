"""Чем один проект отличается от другого. Всё остальное в боте общее, так что для нового проекта
достаточно другого Project: его собирает config из переменных окружения."""

from collections.abc import Mapping
from dataclasses import dataclass, field

from bot.domain.models import ReviewRequests


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

    def reviewers(self, requests: ReviewRequests) -> tuple[str, ...]:
        """Логины людей, которых попросили о ревью, вместе с участниками запрошенных команд."""
        unique: dict[str, str] = {}
        for login in (*requests.users, *(login for team in requests.teams for login in self.team_members(team))):
            unique.setdefault(login.lower(), login)  # логины GitHub не зависят от регистра
        return tuple(unique.values())

    def unknown_teams(self, requests: ReviewRequests) -> tuple[str, ...]:
        """Запрошенные команды, чей состав не задан: их некого отметить."""
        return tuple(team for team in requests.teams if not self.team_members(team))

    def team_url(self, team: str) -> str:
        return f"https://github.com/orgs/{self.org}/teams/{team}"

    def short_repo(self, name: str) -> str:
        return name.removeprefix(self.repo_prefix)
