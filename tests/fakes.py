"""Подделки внешних систем для тестов сервисов и наблюдателя."""

from datetime import datetime

from bot.domain.models import FailedJob, PullRequest, PullRequestComment, Review, ReviewComment, WorkflowRun
from bot.github import NotFoundError


class FakeGitHub:
    def __init__(self) -> None:
        self.pulls: list[PullRequest] = []
        self.old_pulls: list[PullRequest] = []  # не попадают в список недавних
        self.reviews: dict[int, list[Review]] = {}
        self.review_comments: list[ReviewComment] = []
        self.pr_comments: list[PullRequestComment] = []
        self.runs: list[WorkflowRun] = []
        self.jobs: dict[int, list[FailedJob]] = {}
        self.merged: dict[str, list[PullRequest]] = {}
        self.users: set[str] = set()
        self.fetched_pulls: list[int] = []
        self.fetched_jobs: list[int] = []

    async def recent_pulls(self, repo: str) -> list[PullRequest]:
        return self.pulls

    async def pull(self, repo: str, number: int) -> PullRequest:
        self.fetched_pulls.append(number)
        return next(pr for pr in [*self.pulls, *self.old_pulls] if pr.number == number)

    async def pull_reviews(self, repo: str, number: int) -> list[Review]:
        return self.reviews.get(number, [])

    async def recent_review_comments(self, repo: str) -> list[ReviewComment]:
        return self.review_comments

    async def recent_pull_request_comments(self, repo: str) -> list[PullRequestComment]:
        return self.pr_comments

    async def finished_runs(self, repo: str) -> list[WorkflowRun]:
        return self.runs

    async def failed_jobs(self, repo: str, run_id: int) -> list[FailedJob]:
        self.fetched_jobs.append(run_id)
        return self.jobs.get(run_id, [])

    async def merged_pulls(self, repo: str, since: datetime, until: datetime) -> list[PullRequest]:
        return [pr for pr in self.merged.get(repo, []) if pr.merged_at and since <= pr.merged_at <= until]

    async def user_login(self, login: str) -> str:
        for known in self.users:
            if known.lower() == login.lower():
                return known
        raise NotFoundError(login)


class FakeRedmine:
    def __init__(self, subjects: dict[int, str] | None = None) -> None:
        self._subjects = subjects or {}

    def issue_url(self, issue_id: int) -> str:
        return f"https://ai.nsu.ru/issues/{issue_id}"

    async def subjects(self, issue_ids: set[int]) -> dict[int, str]:
        return {i: s for i, s in self._subjects.items() if i in issue_ids}
