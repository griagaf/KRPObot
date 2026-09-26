import asyncio
from datetime import date
from zoneinfo import ZoneInfo

import pytest

from bot.changelog import ChangelogService
from bot.telegram import changelog_view
from bot.telegram.markup import split_messages
from bot.telegram.period import parse_period
from tests import factories as f
from tests.fakes import FakeGitHub, FakeRedmine

TODAY = date(2026, 10, 12)
TZ = ZoneInfo("Asia/Novosibirsk")


def build(github, redmine=None, since=date(2026, 9, 29), until=TODAY):
    service = ChangelogService(github, redmine or FakeRedmine(), ["dejaview-backend", "dejaview-frontend"], TZ)
    return asyncio.run(service.build(since, until))


def test_changelog_groups_merged_pulls_and_adds_task_subjects():
    github = FakeGitHub()
    github.merged = {
        "dejaview-backend": [f.merged_pr(1, title="fix: падение при пустом запросе", branch="fix-empty")],
        "dejaview-frontend": [f.merged_pr(2, title="feat: страница поиска", branch="feature/17624-search-page")],
    }
    changelog = build(github, FakeRedmine({17624: "Дизайн-макет"}))
    assert [kind for kind, _ in changelog.sections()] == ["feat", "fix"]

    [text] = changelog_view.render(changelog, f.view())
    assert text.index("Новое") < text.index("страница поиска") < text.index("Исправления")
    assert '<a href="https://ai.nsu.ru/issues/17624">#17624</a> Дизайн-макет' in text
    assert "<b>frontend</b>" in text


def test_period_boundaries_follow_local_timezone():
    github = FakeGitHub()
    # 29.09 00:30 по Новосибирску — это ещё 28.09 по UTC
    github.merged = {"dejaview-backend": [f.merged_pr(1, at="2026-09-28T17:30:00Z")]}
    assert len(build(github).entries) == 1
    assert build(github, since=date(2026, 9, 30)).entries == ()


def test_empty_changelog():
    [text] = changelog_view.render(build(FakeGitHub()), f.view())
    assert "ничего не влито" in text


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        ("", (date(2026, 9, 29), TODAY)),
        ("7d", (date(2026, 10, 6), TODAY)),
        ("29.09", (date(2026, 9, 29), TODAY)),
        ("2026-09-29 2026-10-05", (date(2026, 9, 29), date(2026, 10, 5))),
        ("29.09.2026 05.10", (date(2026, 9, 29), date(2026, 10, 5))),
    ],
)
def test_parse_period(args, expected):
    assert parse_period(args, TODAY) == expected


@pytest.mark.parametrize("args", ["вчера", "12.10 29.09", "1 2 3"])
def test_parse_period_rejects(args):
    with pytest.raises(ValueError):
        parse_period(args, TODAY)


def test_split_messages_respects_limit():
    chunks = split_messages(["x" * 40] * 10, limit=100)
    assert all(len(c) <= 100 for c in chunks)
    assert "\n".join(chunks).count("x") == 400
