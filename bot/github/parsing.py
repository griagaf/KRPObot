"""JSON GitHub REST API → модели. Единственное место, которое знает форму ответов GitHub."""

from datetime import datetime
from typing import Any

from bot.domain.models import (
    FAILED_CONCLUSIONS,
    FailedJob,
    PullRequest,
    PullRequestComment,
    Review,
    ReviewComment,
    User,
    WorkflowRun,
)

Json = dict[str, Any]


def _time(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _optional_time(value: str | None) -> datetime | None:
    return _time(value) if value else None


def _number_from_url(url: str) -> int:
    return int(url.rstrip("/").rsplit("/", 1)[1])


def user(data: Json) -> User:
    return User(data["login"], is_bot=data.get("type") == "Bot")


def pull_request(data: Json) -> PullRequest:
    return PullRequest(
        id=data["id"],
        number=data["number"],
        title=data["title"],
        body=data.get("body") or "",
        url=data["html_url"],
        author=user(data["user"]),
        head=data["head"]["ref"],
        base=data["base"]["ref"],
        is_open=data["state"] == "open",
        is_draft=bool(data.get("draft")),
        requested_reviewers=tuple(sorted(u["login"] for u in data.get("requested_reviewers") or [])),
        created_at=_time(data["created_at"]),
        updated_at=_time(data["updated_at"]),
        closed_at=_optional_time(data.get("closed_at")),
        merged_at=_optional_time(data.get("merged_at")),
    )


def review(data: Json) -> Review | None:
    """None для черновика ревью: его видит только автор, и он ещё не отправлен."""
    if data["state"] == "PENDING" or not data.get("submitted_at"):
        return None
    return Review(
        id=data["id"],
        state=data["state"],
        body=data.get("body") or "",
        author=user(data["user"]),
        url=data["html_url"],
        submitted_at=_time(data["submitted_at"]),
    )


def review_comment(data: Json) -> ReviewComment:
    return ReviewComment(
        id=data["id"],
        review_id=data.get("pull_request_review_id"),
        pr_number=_number_from_url(data["pull_request_url"]),
        path=data.get("path"),
        body=data.get("body") or "",
        author=user(data["user"]),
        url=data["html_url"],
        created_at=_time(data["created_at"]),
    )


def pull_request_comment(data: Json) -> PullRequestComment | None:
    """None для комментария к обычной задаче: GitHub отдаёт их одним списком с комментариями PR."""
    if "/pull/" not in data["html_url"]:
        return None
    return PullRequestComment(
        id=data["id"],
        pr_number=_number_from_url(data["issue_url"]),
        body=data.get("body") or "",
        author=user(data["user"]),
        url=data["html_url"],
        created_at=_time(data["created_at"]),
    )


def workflow_run(data: Json) -> WorkflowRun:
    return WorkflowRun(
        id=data["id"],
        attempt=data.get("run_attempt") or 1,
        workflow=data["name"],
        number=data["run_number"],
        conclusion=data.get("conclusion"),
        branch=data.get("head_branch") or "",
        title=data.get("display_title") or "",
        url=data["html_url"],
        repo_url=data["repository"]["html_url"],
        actor=user(data["actor"]),
        pr_numbers=tuple(pr["number"] for pr in data.get("pull_requests") or []),
        started_at=_time(data.get("run_started_at") or data["created_at"]),
        finished_at=_time(data["updated_at"]),
    )


def failed_job(data: Json) -> FailedJob | None:
    if data.get("conclusion") not in FAILED_CONCLUSIONS:
        return None
    steps = data.get("steps") or []
    step = next((s["name"] for s in steps if s.get("conclusion") in FAILED_CONCLUSIONS), None)
    return FailedJob(data["name"], step)
