import asyncio
import sqlite3
from datetime import UTC, datetime

import pytest

from bot.domain.events import BuildFinished, PullRequestMerged, PullRequestOpened, ReviewSubmitted
from bot.watcher import RepoScanner, Watcher, WatchState
from tests import factories as f
from tests.fakes import FakeGitHub

WATCH_START = datetime(2026, 10, 1, tzinfo=UTC)


class Recorder:
    def __init__(self):
        self.events = []
        self.down = False

    async def handle(self, event):
        if self.down:
            raise ConnectionError("telegram недоступен")
        self.events.append(event)


@pytest.fixture
def setup():
    github = FakeGitHub()
    github.pulls = [f.pr()]
    state = WatchState(sqlite3.connect(":memory:"))
    handler = Recorder()
    watcher = Watcher(RepoScanner(github, state), state, ["r"], [handler], interval=60, clock=lambda: WATCH_START)
    return github, handler, lambda: asyncio.run(watcher.poll("r"))


def test_first_poll_is_silent_then_only_new_events_are_handled(setup):
    github, handler, poll = setup
    github.runs = [f.run(1, conclusion="failure")]
    poll()
    assert handler.events == []

    github.pulls = [f.pr(updated_at="2026-10-01T11:00:00Z")]
    github.reviews = {12: [f.review(5)]}
    github.runs = [f.run(1, conclusion="failure"), f.run(2, conclusion="failure")]
    poll()
    assert [type(e) for e in handler.events] == [BuildFinished, ReviewSubmitted]
    assert handler.events[0].run.id == 2

    poll()
    assert len(handler.events) == 2


def test_new_pull_request_opened_and_merged(setup):
    github, handler, poll = setup
    poll()
    github.pulls.append(f.merged_pr(13, created_at="2026-10-01T11:00:00Z", at="2026-10-01T12:00:00Z"))
    poll()
    assert [type(e) for e in handler.events] == [PullRequestOpened, PullRequestMerged]


def test_events_older_than_watch_start_are_skipped(setup):
    github, handler, poll = setup
    poll()
    github.pulls.append(f.merged_pr(14, created_at="2026-08-30T00:00:00Z", at="2026-09-01T00:00:00Z"))
    poll()
    assert handler.events == []


def test_failed_handler_gets_the_event_again(setup):
    github, handler, poll = setup
    poll()
    github.pulls = [f.pr(updated_at="2026-10-01T11:00:00Z")]
    github.reviews = {12: [f.review(5)]}

    handler.down = True
    with pytest.raises(ConnectionError):
        poll()
    handler.down = False
    poll()
    assert [type(e) for e in handler.events] == [ReviewSubmitted]
