import asyncio
import sqlite3

import pytest

from bot.domain.codeowners import CodeOwners
from bot.domain.events import (
    BuildFinished,
    CodeCommented,
    PullRequestClosed,
    PullRequestCommented,
    PullRequestMerged,
    PullRequestOpened,
    ReviewRequested,
    ReviewSubmitted,
)
from bot.domain.models import FailedJob, ReviewRequests
from bot.watcher import RepoScanner, WatchState
from bot.watcher.scanner import added_review_requests, group_review_comments
from tests import factories as f
from tests.fakes import FakeGitHub

REPO = "dejaview-backend"


@pytest.fixture
def github():
    return FakeGitHub()


@pytest.fixture
def state():
    return WatchState(sqlite3.connect(":memory:"))


def scan(github, state, *, fetch_details=True):
    return asyncio.run(RepoScanner(github, state).scan(REPO, fetch_details=fetch_details))


def test_group_review_comments_by_review_then_by_pr_and_author():
    comments = [
        f.review_comment(1, review_id=10),
        f.review_comment(2, review_id=99, author="a"),
        f.review_comment(3, review_id=98, author="a"),
        f.review_comment(4, review_id=97, author="b"),
    ]
    attached, orphans = group_review_comments([f.review(10)], comments)
    assert [c.id for c in attached[10]] == [1]
    assert sorted([c.id for c in group] for group in orphans) == [[2, 3], [4]]


def test_added_review_requests():
    pr = f.pr(reviewers=("a", "b"), teams=("maintainers",))
    assert added_review_requests(pr, ReviewRequests(users=("a",))) == ReviewRequests(("b",), ("maintainers",))
    assert added_review_requests(pr, pr.review_requests) == ReviewRequests()
    assert not added_review_requests(pr, None)


def test_pull_request_lifecycle(github, state):
    github.pulls = [f.pr(1), f.merged_pr(2), f.pr(3, state="closed", closed_at="2026-10-02T00:00:00Z")]
    events = scan(github, state)
    assert [type(e) for e in events.events if e.pr.number == 2] == [PullRequestOpened, PullRequestMerged]
    assert any(isinstance(e, PullRequestClosed) and e.pr.number == 3 for e in events.events)


def test_review_request_is_detected_against_remembered_reviewers(github, state):
    github.pulls = [f.pr()]
    state.mark_seen(e.keys[0] for e in scan(github, state).events)
    state.remember_pulls(github.pulls)
    github.pulls = [f.pr(reviewers=("mentor",), updated_at="2026-10-01T13:00:00Z")]
    [event] = scan(github, state).events
    assert isinstance(event, ReviewRequested) and event.requests == ReviewRequests(users=("mentor",))


def test_review_carries_its_code_comments_and_other_comments_are_grouped(github, state):
    github.pulls = [f.pr()]
    github.reviews = {12: [f.review(5)]}
    github.review_comments = [f.review_comment(7, review_id=5), f.review_comment(8, review_id=6, author="a")]
    events = scan(github, state).events
    [review] = [e for e in events if isinstance(e, ReviewSubmitted)]
    [orphan] = [e for e in events if isinstance(e, CodeCommented)]
    assert [c.id for c in review.comments] == [7]
    assert [c.id for c in orphan.comments] == [8]


def test_seen_items_are_not_reported_again(github, state):
    github.pulls = [f.pr()]
    github.reviews = {12: [f.review(5)]}
    github.pr_comments = [f.pr_comment(9)]
    github.runs = [f.run(1)]
    first = scan(github, state)
    for event in first.events:
        state.mark_seen(event.keys)
    state.remember_pulls(first.pulls)
    assert scan(github, state).events == ()


def test_comment_in_old_pull_request_fetches_it(github, state):
    github.pulls = [f.pr()]
    github.old_pulls = [f.pr(3)]
    github.pr_comments = [f.pr_comment(9, number=3), f.pr_comment(10, number=12)]
    events = scan(github, state).events
    commented = sorted(e.pr.number for e in events if isinstance(e, PullRequestCommented))
    assert commented == [3, 12]
    assert github.fetched_pulls == [3]


def test_failed_build_details_are_fetched_only_when_needed(github, state):
    github.runs = [f.run(1, conclusion="failure"), f.run(2)]
    github.jobs = {1: [FailedJob("build", "Run tests")]}
    assert scan(github, state, fetch_details=False).events[0].failed_jobs == ()
    [failed, _] = scan(github, state).events
    assert isinstance(failed, BuildFinished) and failed.failed_jobs == (FailedJob("build", "Run tests"),)
    assert github.fetched_jobs == [1]


def test_remembered_reviewers_of_previous_version_are_read():
    db = sqlite3.connect(":memory:")
    state = WatchState(db)
    db.execute("INSERT INTO pull_requests VALUES (1012, '2026-10-01T10:00:00+00:00', '[\"mentor\"]')")
    assert state.known_review_requests(1012) == ReviewRequests(users=("mentor",))


ML_CODEOWNERS = CodeOwners.parse("* @skpntsv @dejaview-nsu/maintainers\n/docs/ @writer")


def test_team_review_request_brings_owners_of_changed_files(github, state):
    github.codeowners = ML_CODEOWNERS
    github.pulls = [f.pr(teams=("maintainers",))]
    github.files = {12: ["src/model.py", "docs/api.md"]}
    [event] = scan(github, state).events
    assert isinstance(event, PullRequestOpened)
    assert event.code_owners == ReviewRequests(("skpntsv", "writer"), ("maintainers",))
    assert github.fetched_codeowners == ["main"]  # CODEOWNERS базовой ветки, как у GitHub


@pytest.mark.parametrize(
    ("pr", "fetch_details"),
    [
        (f.pr(reviewers=("mentor",)), True),  # команду не просили — владельцы не нужны
        (f.pr(teams=("maintainers",), draft=True), True),  # черновик никого не отмечает
        (f.pr(teams=("maintainers",)), False),  # первый проход: событие не опубликуют
    ],
)
def test_owners_are_fetched_only_when_they_matter(github, state, pr, fetch_details):
    github.codeowners = ML_CODEOWNERS
    github.pulls = [pr]
    [event] = scan(github, state, fetch_details=fetch_details).events
    assert event.code_owners == ReviewRequests()
    assert github.fetched_codeowners == []


def test_team_added_later_brings_owners_too(github, state):
    github.pulls = [f.pr()]
    state.mark_seen(e.keys[0] for e in scan(github, state).events)
    state.remember_pulls(github.pulls)
    github.codeowners = ML_CODEOWNERS
    github.files = {12: ["src/model.py"]}
    github.pulls = [f.pr(teams=("maintainers",), updated_at="2026-10-01T13:00:00Z")]
    [event] = scan(github, state).events
    assert isinstance(event, ReviewRequested) and event.code_owners.users == ("skpntsv",)
