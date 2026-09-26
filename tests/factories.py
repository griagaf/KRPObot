"""JSON в форме ответов GitHub и модели из него через настоящий парсер."""

import sqlite3
from typing import Any

from bot.domain.models import PullRequest, PullRequestComment, Review, ReviewComment, WorkflowRun
from bot.github import parsing
from bot.people import PeopleStore, Person
from bot.telegram.view import View

REPO_URL = "https://github.com/dejaview-nsu/dejaview-backend"
API_URL = "https://api.github.com/repos/dejaview-nsu/dejaview-backend"
Json = dict[str, Any]


def user_json(login: str, *, bot: bool = False) -> Json:
    return {"login": login, "type": "Bot" if bot else "User"}


def pr_json(
    number: int = 12,
    *,
    title: str = "feat: API поиска по изображению",
    branch: str = "feature/17653-image-search",
    state: str = "open",
    merged_at: str | None = None,
    closed_at: str | None = None,
    created_at: str = "2026-10-01T09:00:00Z",
    updated_at: str = "2026-10-01T10:00:00Z",
    body: str = "",
    draft: bool = False,
    author: str = "student",
    reviewers: tuple[str, ...] = (),
) -> Json:
    return {
        "id": 1000 + number,
        "number": number,
        "title": title,
        "body": body,
        "draft": draft,
        "state": state,
        "html_url": f"{REPO_URL}/pull/{number}",
        "user": user_json(author),
        "requested_reviewers": [user_json(r) for r in reviewers],
        "head": {"ref": branch},
        "base": {"ref": "main"},
        "created_at": created_at,
        "updated_at": updated_at,
        "closed_at": closed_at,
        "merged_at": merged_at,
    }


def pr(number: int = 12, **kwargs: Any) -> PullRequest:
    return parsing.pull_request(pr_json(number, **kwargs))


def merged_pr(number: int = 12, at: str = "2026-10-02T00:00:00Z", **kwargs: Any) -> PullRequest:
    return pr(number, state="closed", merged_at=at, closed_at=at, updated_at=at, **kwargs)


def review_json(
    review_id: int = 1,
    *,
    state: str = "APPROVED",
    body: str = "",
    author: str = "mentor",
    at: str | None = "2026-10-01T11:00:00Z",
    bot: bool = False,
) -> Json:
    return {
        "id": review_id,
        "state": state,
        "body": body,
        "user": user_json(author, bot=bot),
        "html_url": f"{REPO_URL}/pull/12#pullrequestreview-{review_id}",
        "submitted_at": at,
    }


def review(review_id: int = 1, **kwargs: Any) -> Review:
    parsed = parsing.review(review_json(review_id, **kwargs))
    assert parsed is not None
    return parsed


def review_comment_json(
    comment_id: int = 1,
    *,
    review_id: int = 1,
    pr_number: int = 12,
    body: str = "Тут утечка",
    author: str = "mentor",
    path: str = "src/search.cpp",
    at: str = "2026-10-01T11:00:00Z",
    bot: bool = False,
) -> Json:
    return {
        "id": comment_id,
        "pull_request_review_id": review_id,
        "pull_request_url": f"{API_URL}/pulls/{pr_number}",
        "path": path,
        "body": body,
        "user": user_json(author, bot=bot),
        "html_url": f"{REPO_URL}/pull/{pr_number}#discussion_r{comment_id}",
        "created_at": at,
    }


def review_comment(comment_id: int = 1, **kwargs: Any) -> ReviewComment:
    return parsing.review_comment(review_comment_json(comment_id, **kwargs))


def issue_comment_json(
    comment_id: int = 1,
    *,
    number: int = 12,
    is_pr: bool = True,
    body: str = "Поправил",
    author: str = "mentor",
    at: str = "2026-10-01T12:00:00Z",
    bot: bool = False,
) -> Json:
    kind = "pull" if is_pr else "issues"
    return {
        "id": comment_id,
        "issue_url": f"{API_URL}/issues/{number}",
        "html_url": f"{REPO_URL}/{kind}/{number}#issuecomment-{comment_id}",
        "body": body,
        "user": user_json(author, bot=bot),
        "created_at": at,
    }


def pr_comment(comment_id: int = 1, **kwargs: Any) -> PullRequestComment:
    parsed = parsing.pull_request_comment(issue_comment_json(comment_id, **kwargs))
    assert parsed is not None
    return parsed


def run_json(
    run_id: int = 1,
    *,
    conclusion: str = "success",
    attempt: int = 1,
    pull_requests: tuple[int, ...] = (),
    actor: str = "student",
    finished_at: str = "2026-10-01T10:02:13Z",
) -> Json:
    return {
        "id": run_id,
        "name": "CI",
        "run_number": 57,
        "run_attempt": attempt,
        "status": "completed",
        "conclusion": conclusion,
        "head_branch": "feature/17653-image-search",
        "display_title": "feat: API поиска по изображению",
        "html_url": f"{REPO_URL}/actions/runs/{run_id}",
        "repository": {"html_url": REPO_URL},
        "actor": user_json(actor),
        "pull_requests": [{"number": n} for n in pull_requests],
        "created_at": "2026-10-01T10:00:00Z",
        "run_started_at": "2026-10-01T10:00:00Z",
        "updated_at": finished_at,
    }


def run(run_id: int = 1, **kwargs: Any) -> WorkflowRun:
    return parsing.workflow_run(run_json(run_id, **kwargs))


def job_json(name: str, conclusion: str = "success", failed_step: str | None = None) -> Json:
    steps = [{"name": "Checkout", "conclusion": "success"}]
    if failed_step:
        steps.append({"name": failed_step, "conclusion": "failure"})
    return {"name": name, "conclusion": conclusion, "steps": steps}


def people(linked: tuple[str, ...] = ()) -> PeopleStore:
    """linked: логины со связкой в Telegram; tg_id по порядку с 1, имя — логин с заглавной."""
    store = PeopleStore(sqlite3.connect(":memory:"))
    for tg_id, login in enumerate(linked, start=1):
        store.save(Person(login, tg_id, login.capitalize()))
    return store


def view(linked: tuple[str, ...] = ()) -> View:
    return View(people(linked), lambda task: f"https://ai.nsu.ru/issues/{task}", "dejaview-nsu")
