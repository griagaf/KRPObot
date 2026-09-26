from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from bot.domain.conventions import CHANGE_KINDS, OTHER_KIND, ChangeTitle, task_id
from bot.domain.models import PullRequest
from bot.github import GitHubClient
from bot.redmine import RedmineClient


@dataclass(frozen=True)
class ChangelogEntry:
    repo: str
    pr: PullRequest
    change: ChangeTitle
    task: int | None
    task_subject: str | None


@dataclass(frozen=True)
class Changelog:
    since: date
    until: date
    entries: tuple[ChangelogEntry, ...]

    def sections(self) -> list[tuple[str, list[ChangelogEntry]]]:
        """Непустые разделы в порядке важности; внутри — по репозиторию и времени слияния."""
        result = []
        for kind in (*CHANGE_KINDS, OTHER_KIND):
            entries = sorted(
                (e for e in self.entries if e.change.kind == kind),
                key=lambda e: (e.repo, e.pr.finished_at),
            )
            if entries:
                result.append((kind, entries))
        return result


class ChangelogService:
    """Changelog по PR, влитым за период во все отслеживаемые репозитории."""

    def __init__(self, github: GitHubClient, redmine: RedmineClient, repos: Sequence[str], tz: ZoneInfo) -> None:
        self._github = github
        self._redmine = redmine
        self._repos = repos
        self._tz = tz

    async def build(self, since: date, until: date) -> Changelog:
        start = datetime.combine(since, time.min, self._tz)
        end = datetime.combine(until, time.max, self._tz)
        merged = [(repo, pr) for repo in self._repos for pr in await self._github.merged_pulls(repo, start, end)]
        tasks = [task_id(pr) for _, pr in merged]
        subjects = await self._redmine.subjects({task for task in tasks if task})
        entries = tuple(
            ChangelogEntry(repo, pr, ChangeTitle.parse(pr.title), task, subjects.get(task) if task else None)
            for (repo, pr), task in zip(merged, tasks, strict=True)
        )
        return Changelog(since, until, entries)
