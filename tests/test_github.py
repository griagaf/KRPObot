import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from bot.github import GitHubClient, GitHubError, NotFoundError, parsing
from tests import factories as f

FIXTURES = Path(__file__).parent / "fixtures"


def test_parses_real_pull_request_response():
    pr = parsing.pull_request(json.loads((FIXTURES / "pull.json").read_text(encoding="utf-8")))
    assert (pr.number, pr.head, pr.base, pr.author.is_bot) == (1, "docs/actualize-2026-09", "main", False)
    assert not pr.is_open
    assert pr.merged_at == datetime(2026, 9, 20, 5, 4, 4, tzinfo=UTC)


def test_pending_review_and_issue_comment_are_skipped():
    assert parsing.review(f.review_json(state="PENDING", at=None)) is None
    assert parsing.pull_request_comment(f.issue_comment_json(is_pr=False)) is None


def test_workflow_run():
    run = parsing.workflow_run(f.run_json(conclusion="failure", pull_requests=(12,)))
    assert run.failed and not run.succeeded
    assert run.duration.total_seconds() == 133
    assert run.pr_url(12) == f"{f.REPO_URL}/pull/12"


def test_failed_job_names_first_failed_step():
    assert parsing.failed_job(f.job_json("lint")) is None
    job = parsing.failed_job(f.job_json("build", "failure", "Run tests"))
    assert job is not None and (job.name, job.step) == ("build", "Run tests")


def client(handler) -> GitHubClient:
    return GitHubClient("token", "dejaview-nsu", transport=httpx.MockTransport(handler))


def test_polling_uses_etag_and_returns_cached_body_on_304():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.headers.get("If-None-Match") == '"v1"':
            return httpx.Response(304)
        return httpx.Response(200, json=[f.pr_json()], headers={"ETag": '"v1"'})

    async def scenario():
        async with client(handler) as github:
            return await github.recent_pulls("dejaview-backend"), await github.recent_pulls("dejaview-backend")

    first, second = asyncio.run(scenario())
    assert first == second and first[0].number == 12
    assert requests[0].headers["Authorization"] == "Bearer token"
    assert requests[1].headers["If-None-Match"] == '"v1"'


@pytest.mark.parametrize(
    ("response", "error"),
    [(httpx.Response(404), NotFoundError), (httpx.Response(502), GitHubError)],
)
def test_http_errors_become_github_errors(response, error):
    async def scenario():
        async with client(lambda request: response) as github:
            await github.user_login("ghost")

    with pytest.raises(error):
        asyncio.run(scenario())


def test_network_error_becomes_github_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    async def scenario():
        async with client(handler) as github:
            await github.org_repos()

    with pytest.raises(GitHubError):
        asyncio.run(scenario())


def test_merged_pulls_stops_paging_once_older_than_period():
    pages = []

    def merged(number: int, at: str) -> dict:
        return f.pr_json(number, state="closed", merged_at=at, closed_at=at, updated_at=at)

    def handler(request: httpx.Request) -> httpx.Response:
        pages.append(request.url.params["page"])
        in_period = [merged(n, "2026-10-05T00:00:00Z") for n in range(99)]
        return httpx.Response(200, json=[*in_period, merged(99, "2026-01-01T00:00:00Z")])

    async def scenario():
        async with client(handler) as github:
            return await github.merged_pulls(
                "dejaview-backend", datetime(2026, 10, 1, tzinfo=UTC), datetime(2026, 10, 12, tzinfo=UTC)
            )

    result = asyncio.run(scenario())
    assert len(result) == 99
    assert pages == ["1"]
