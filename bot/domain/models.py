"""Что бот знает о GitHub, без подробностей его API."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum


@dataclass(frozen=True)
class User:
    login: str
    is_bot: bool = False


@dataclass(frozen=True)
class ReviewRequests:
    """Кого попросили о ревью: людей и команды GitHub. Команды обычно назначает CODEOWNERS."""

    users: tuple[str, ...] = ()
    teams: tuple[str, ...] = ()

    def __bool__(self) -> bool:
        return bool(self.users or self.teams)

    def added_since(self, known: "ReviewRequests") -> "ReviewRequests":
        return ReviewRequests(
            tuple(u for u in self.users if u not in known.users),
            tuple(t for t in self.teams if t not in known.teams),
        )


@dataclass(frozen=True)
class PullRequest:
    id: int
    number: int
    title: str
    body: str
    url: str
    author: User
    head: str
    base: str
    is_open: bool
    is_draft: bool
    review_requests: ReviewRequests
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None
    merged_at: datetime | None

    @property
    def finished_at(self) -> datetime:
        return self.merged_at or self.closed_at or self.updated_at


class ReviewState(StrEnum):
    APPROVED = "APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    COMMENTED = "COMMENTED"
    DISMISSED = "DISMISSED"


@dataclass(frozen=True)
class Review:
    id: int
    state: str  # значение ReviewState; строка, чтобы новое состояние в GitHub не ломало разбор
    body: str
    author: User
    url: str
    submitted_at: datetime


@dataclass(frozen=True)
class ReviewComment:
    """Комментарий к строке кода в PR."""

    id: int
    review_id: int | None
    pr_number: int
    path: str | None
    body: str
    author: User
    url: str
    created_at: datetime


@dataclass(frozen=True)
class PullRequestComment:
    """Комментарий в обсуждении PR."""

    id: int
    pr_number: int
    body: str
    author: User
    url: str
    created_at: datetime


FAILED_CONCLUSIONS = frozenset({"failure", "timed_out", "startup_failure"})


@dataclass(frozen=True)
class WorkflowRun:
    """Завершённый запуск GitHub Actions."""

    id: int
    attempt: int
    workflow: str
    number: int
    conclusion: str | None
    branch: str
    title: str
    url: str
    repo_url: str
    actor: User
    pr_numbers: tuple[int, ...]
    started_at: datetime
    finished_at: datetime

    @property
    def failed(self) -> bool:
        return self.conclusion in FAILED_CONCLUSIONS

    @property
    def succeeded(self) -> bool:
        return self.conclusion == "success"

    @property
    def duration(self) -> timedelta:
        return max(self.finished_at - self.started_at, timedelta())

    def pr_url(self, number: int) -> str:
        return f"{self.repo_url}/pull/{number}"


@dataclass(frozen=True)
class FailedJob:
    name: str
    step: str | None
