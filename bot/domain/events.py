"""События в репозиториях. Сканер их находит, обработчики реагируют: чат, в будущем Redmine."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from bot.domain.models import FailedJob, PullRequest, PullRequestComment, Review, ReviewComment, WorkflowRun


def pr_opened_key(pr: PullRequest) -> str:
    return f"pr-open:{pr.id}"


def pr_finished_key(pr: PullRequest) -> str:
    # closed_at в ключе: переоткрытый и снова влитый PR — новое событие
    return f"pr-close:{pr.id}:{pr.closed_at.isoformat() if pr.closed_at else ''}"


def review_key(review_id: int) -> str:
    return f"review:{review_id}"


def review_comment_key(comment_id: int) -> str:
    return f"rc:{comment_id}"


def pr_comment_key(comment_id: int) -> str:
    return f"ic:{comment_id}"


def run_key(run: WorkflowRun) -> str:
    return f"run:{run.id}:{run.attempt}"


@dataclass(frozen=True)
class RepoEvent(ABC):
    repo: str

    @property
    @abstractmethod
    def keys(self) -> tuple[str, ...]:
        """Ключи защиты от повторов: самого события и всего, что в него вошло."""

    @property
    @abstractmethod
    def occurred_at(self) -> datetime: ...


@dataclass(frozen=True)
class PullRequestOpened(RepoEvent):
    pr: PullRequest

    @property
    def keys(self) -> tuple[str, ...]:
        return (pr_opened_key(self.pr),)

    @property
    def occurred_at(self) -> datetime:
        return self.pr.created_at


@dataclass(frozen=True)
class ReviewRequested(RepoEvent):
    pr: PullRequest
    reviewers: tuple[str, ...]

    @property
    def keys(self) -> tuple[str, ...]:
        return (f"review-request:{self.pr.id}:{self.pr.updated_at.isoformat()}",)

    @property
    def occurred_at(self) -> datetime:
        return self.pr.updated_at


@dataclass(frozen=True)
class PullRequestMerged(RepoEvent):
    pr: PullRequest

    @property
    def keys(self) -> tuple[str, ...]:
        return (pr_finished_key(self.pr),)

    @property
    def occurred_at(self) -> datetime:
        return self.pr.finished_at


@dataclass(frozen=True)
class PullRequestClosed(RepoEvent):
    """PR закрыт без слияния."""

    pr: PullRequest

    @property
    def keys(self) -> tuple[str, ...]:
        return (pr_finished_key(self.pr),)

    @property
    def occurred_at(self) -> datetime:
        return self.pr.finished_at


@dataclass(frozen=True)
class ReviewSubmitted(RepoEvent):
    pr: PullRequest
    review: Review
    comments: tuple[ReviewComment, ...]

    @property
    def keys(self) -> tuple[str, ...]:
        return (review_key(self.review.id), *(review_comment_key(c.id) for c in self.comments))

    @property
    def occurred_at(self) -> datetime:
        return self.review.submitted_at


@dataclass(frozen=True)
class CodeCommented(RepoEvent):
    """Комментарии одного автора к коду вне нового ревью, например ответы в обсуждении строки."""

    pr: PullRequest
    comments: tuple[ReviewComment, ...]

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(review_comment_key(c.id) for c in self.comments)

    @property
    def occurred_at(self) -> datetime:
        return self.comments[-1].created_at


@dataclass(frozen=True)
class PullRequestCommented(RepoEvent):
    pr: PullRequest
    comment: PullRequestComment

    @property
    def keys(self) -> tuple[str, ...]:
        return (pr_comment_key(self.comment.id),)

    @property
    def occurred_at(self) -> datetime:
        return self.comment.created_at


@dataclass(frozen=True)
class BuildFinished(RepoEvent):
    run: WorkflowRun
    failed_jobs: tuple[FailedJob, ...] = ()

    @property
    def keys(self) -> tuple[str, ...]:
        return (run_key(self.run),)

    @property
    def occurred_at(self) -> datetime:
        return self.run.finished_at
