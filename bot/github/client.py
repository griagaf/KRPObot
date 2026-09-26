from datetime import datetime
from types import TracebackType
from typing import Any, Self
from urllib.parse import urlencode

import httpx

from bot.domain.models import FailedJob, PullRequest, PullRequestComment, Review, ReviewComment, WorkflowRun
from bot.github import parsing

API_URL = "https://api.github.com"
PAGE_SIZE = 100


class GitHubError(Exception):
    """GitHub недоступен или ответил ошибкой."""


class NotFoundError(GitHubError):
    pass


class GitHubClient:
    """REST API организации. Возвращает модели, ошибки сводит к GitHubError."""

    def __init__(self, token: str, org: str, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._http = httpx.AsyncClient(base_url=API_URL, timeout=30, headers=headers, transport=transport)
        self._org = org
        self._etags: dict[str, tuple[str, Any]] = {}

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        await self._http.aclose()

    async def _get(self, path: str, *, conditional: bool = False, **params: Any) -> Any:
        """conditional: запрос с ETag, неизменившийся ответ (304) не тратит лимит API."""
        cache_key = f"{path}?{urlencode(sorted(params.items()))}"
        cached = self._etags.get(cache_key) if conditional else None
        headers = {"If-None-Match": cached[0]} if cached else {}
        try:
            response = await self._http.get(path, params=params, headers=headers)
        except httpx.HTTPError as err:
            raise GitHubError(f"GET {path}: {err!r}") from err

        if response.status_code == httpx.codes.NOT_MODIFIED and cached:
            return cached[1]
        if response.status_code == httpx.codes.NOT_FOUND:
            raise NotFoundError(f"GET {path}: не найдено")
        if response.is_error:
            raise GitHubError(f"GET {path}: HTTP {response.status_code}")

        body = response.json()
        if conditional and (etag := response.headers.get("ETag")):
            self._etags[cache_key] = (etag, body)
        return body

    def _repo(self, repo: str) -> str:
        return f"/repos/{self._org}/{repo}"

    async def org_repos(self) -> list[str]:
        repos = await self._get(f"/orgs/{self._org}/repos", per_page=PAGE_SIZE)
        return [r["name"] for r in repos if not r["archived"]]

    async def user_login(self, login: str) -> str:
        """Логин в том написании, которое хранит GitHub. NotFoundError, если такого нет."""
        user = await self._get(f"/users/{login}")
        return str(user["login"])

    async def recent_pulls(self, repo: str) -> list[PullRequest]:
        pulls = await self._get(
            f"{self._repo(repo)}/pulls",
            conditional=True,
            state="all",
            sort="updated",
            direction="desc",
            per_page=30,
        )
        return [parsing.pull_request(pr) for pr in pulls]

    async def pull(self, repo: str, number: int) -> PullRequest:
        return parsing.pull_request(await self._get(f"{self._repo(repo)}/pulls/{number}"))

    async def pull_reviews(self, repo: str, number: int) -> list[Review]:
        reviews = await self._get(f"{self._repo(repo)}/pulls/{number}/reviews", per_page=PAGE_SIZE)
        return [r for r in map(parsing.review, reviews) if r is not None]

    async def recent_review_comments(self, repo: str) -> list[ReviewComment]:
        comments = await self._get(
            f"{self._repo(repo)}/pulls/comments",
            conditional=True,
            sort="created",
            direction="desc",
            per_page=50,
        )
        return [parsing.review_comment(c) for c in comments]

    async def recent_pull_request_comments(self, repo: str) -> list[PullRequestComment]:
        comments = await self._get(
            f"{self._repo(repo)}/issues/comments",
            conditional=True,
            sort="created",
            direction="desc",
            per_page=50,
        )
        return [c for c in map(parsing.pull_request_comment, comments) if c is not None]

    async def finished_runs(self, repo: str) -> list[WorkflowRun]:
        body = await self._get(f"{self._repo(repo)}/actions/runs", conditional=True, status="completed", per_page=30)
        return [parsing.workflow_run(run) for run in body["workflow_runs"]]

    async def failed_jobs(self, repo: str, run_id: int) -> list[FailedJob]:
        body = await self._get(f"{self._repo(repo)}/actions/runs/{run_id}/jobs", per_page=PAGE_SIZE)
        return [job for job in map(parsing.failed_job, body["jobs"]) if job is not None]

    async def merged_pulls(self, repo: str, since: datetime, until: datetime) -> list[PullRequest]:
        merged: list[PullRequest] = []
        page = 1
        while True:
            batch = [
                parsing.pull_request(pr)
                for pr in await self._get(
                    f"{self._repo(repo)}/pulls",
                    state="closed",
                    sort="updated",
                    direction="desc",
                    per_page=PAGE_SIZE,
                    page=page,
                )
            ]
            merged += [pr for pr in batch if pr.merged_at and since <= pr.merged_at <= until]
            # Список отсортирован по обновлению: дальше идут PR, не менявшиеся с начала периода.
            if len(batch) < PAGE_SIZE or batch[-1].updated_at < since:
                return merged
            page += 1
