from collections import defaultdict
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from bot.domain.events import (
    BuildFinished,
    CodeCommented,
    PullRequestClosed,
    PullRequestCommented,
    PullRequestMerged,
    PullRequestOpened,
    RepoEvent,
    ReviewRequested,
    ReviewSubmitted,
    pr_comment_key,
    pr_finished_key,
    pr_opened_key,
    review_comment_key,
    review_key,
    run_key,
)
from bot.domain.models import PullRequest, Review, ReviewComment, ReviewRequests
from bot.github import GitHubClient
from bot.watcher.state import WatchState


@dataclass(frozen=True)
class Scan:
    events: tuple[RepoEvent, ...]
    pulls: tuple[PullRequest, ...]


def added_review_requests(pr: PullRequest, known: ReviewRequests | None) -> ReviewRequests:
    """Кого попросили о ревью с прошлого опроса. Для незнакомого PR никого: их покажет карточка нового PR."""
    if known is None:
        return ReviewRequests()
    return pr.review_requests.added_since(known)


def group_review_comments(
    reviews: Sequence[Review], comments: Sequence[ReviewComment]
) -> tuple[dict[int, list[ReviewComment]], list[list[ReviewComment]]]:
    """Комментарии к коду по их ревью; остальные — группами по (PR, автор)."""
    review_ids = {r.id for r in reviews}
    attached: dict[int, list[ReviewComment]] = defaultdict(list)
    orphans: dict[tuple[int, str], list[ReviewComment]] = defaultdict(list)
    for comment in sorted(comments, key=lambda c: c.created_at):
        if comment.review_id in review_ids:
            attached[comment.review_id].append(comment)
        else:
            orphans[(comment.pr_number, comment.author.login)].append(comment)
    return attached, list(orphans.values())


class _PullIndex:
    """PR по номеру: из свежего списка, иначе запросом (для обсуждений в давних PR)."""

    def __init__(self, github: GitHubClient, repo: str, pulls: Sequence[PullRequest]) -> None:
        self._github = github
        self._repo = repo
        self._by_number = {pr.number: pr for pr in pulls}

    async def get(self, number: int) -> PullRequest:
        if number not in self._by_number:
            self._by_number[number] = await self._github.pull(self._repo, number)
        return self._by_number[number]


class RepoScanner:
    """Находит новые события репозитория: сравнивает свежие данные GitHub с тем, что уже видели."""

    def __init__(self, github: GitHubClient, state: WatchState) -> None:
        self._github = github
        self._state = state

    async def scan(self, repo: str, *, fetch_details: bool = True) -> Scan:
        """fetch_details=False пропускает дополнительные запросы, когда события не будут опубликованы."""
        pulls = await self._github.recent_pulls(repo)
        index = _PullIndex(self._github, repo, pulls)
        events: list[RepoEvent] = [
            *self._pull_request_events(repo, pulls),
            *await self._build_events(repo, fetch_details=fetch_details),
            *await self._review_events(repo, pulls, index),
            *await self._discussion_events(repo, index),
        ]
        events.sort(key=lambda event: event.occurred_at)
        return Scan(tuple(events), tuple(pulls))

    def _pull_request_events(self, repo: str, pulls: Sequence[PullRequest]) -> Iterator[RepoEvent]:
        for pr in pulls:
            if not self._state.is_seen(pr_opened_key(pr)):
                yield PullRequestOpened(repo, pr)
            elif pr.is_open and (added := added_review_requests(pr, self._state.known_review_requests(pr.id))):
                yield ReviewRequested(repo, pr, added)
            if not pr.is_open and not self._state.is_seen(pr_finished_key(pr)):
                yield PullRequestMerged(repo, pr) if pr.merged_at else PullRequestClosed(repo, pr)

    async def _build_events(self, repo: str, *, fetch_details: bool) -> list[RepoEvent]:
        events: list[RepoEvent] = []
        for run in await self._github.finished_runs(repo):
            if self._state.is_seen(run_key(run)):
                continue
            failed_jobs = await self._github.failed_jobs(repo, run.id) if run.failed and fetch_details else []
            events.append(BuildFinished(repo, run, tuple(failed_jobs)))
        return events

    async def _review_events(self, repo: str, pulls: Sequence[PullRequest], index: _PullIndex) -> list[RepoEvent]:
        comments = [
            c
            for c in await self._github.recent_review_comments(repo)
            if not self._state.is_seen(review_comment_key(c.id))
        ]
        # Ревью нельзя получить по всему репозиторию сразу, поэтому смотрим только изменившиеся PR.
        commented = {c.pr_number for c in comments}
        changed = [pr for pr in pulls if self._state.last_update(pr.id) != pr.updated_at or pr.number in commented]
        reviews = [
            (pr, review)
            for pr in changed
            for review in await self._github.pull_reviews(repo, pr.number)
            if not self._state.is_seen(review_key(review.id))
        ]

        attached, orphans = group_review_comments([review for _, review in reviews], comments)
        events: list[RepoEvent] = [
            ReviewSubmitted(repo, pr, review, tuple(attached.get(review.id, ()))) for pr, review in reviews
        ]
        events += [CodeCommented(repo, await index.get(group[0].pr_number), tuple(group)) for group in orphans]
        return events

    async def _discussion_events(self, repo: str, index: _PullIndex) -> list[RepoEvent]:
        return [
            PullRequestCommented(repo, await index.get(comment.pr_number), comment)
            for comment in await self._github.recent_pull_request_comments(repo)
            if not self._state.is_seen(pr_comment_key(comment.id))
        ]
