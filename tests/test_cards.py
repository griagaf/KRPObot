from dataclasses import replace

from bot.domain.events import (
    BuildFinished,
    PullRequestClosed,
    PullRequestCommented,
    PullRequestMerged,
    PullRequestOpened,
    ReviewRequested,
    ReviewSubmitted,
)
from bot.domain.models import FailedJob, ReviewRequests
from bot.people import Person
from bot.telegram import cards
from bot.telegram.markup import plural
from bot.telegram.view import View
from tests import factories as f

REPO = "dejaview-backend"
PING_STUDENT = '<a href="tg://user?id=1">Student</a>'


def render(event, linked=()):
    return cards.render(event, f.view(linked))


def test_approve_with_code_comments_is_one_card_and_pings_author():
    comments = (f.review_comment(1), f.review_comment(2, body="И тут", path="src/api.cpp"))
    text = render(ReviewSubmitted(REPO, f.pr(), f.review(), comments), ("student",))
    assert text.startswith("✅ <b>Одобрено</b> · #backend")
    assert "2 комментария к коду" in text
    assert "<code>src/search.cpp</code>, <code>src/api.cpp</code>" in text
    assert "Тут утечка" in text
    assert text.endswith(f"🔔 {PING_STUDENT}")


def test_unlinked_person_is_a_github_link_not_a_mention():
    text = render(ReviewSubmitted(REPO, f.pr(), f.review(state="CHANGES_REQUESTED", body="Нужны тесты"), ()))
    assert '🔔 <a href="https://github.com/student">student</a>' in text
    assert "tg://" not in text


def test_actor_is_named_but_not_pinged():
    text = render(ReviewSubmitted(REPO, f.pr(), f.review(), ()), ("student", "mentor"))
    assert "👤 <b>Mentor</b>" in text
    assert "tg://user?id=2" not in text


def test_own_comment_does_not_ping_yourself():
    text = render(PullRequestCommented(REPO, f.pr(), f.pr_comment(author="student")), ("student",))
    assert "🔔" not in text


def test_user_text_is_escaped():
    text = render(PullRequestCommented(REPO, f.pr(title="fix: <script>"), f.pr_comment(body="a < b & c")))
    assert "<script>" not in text
    assert "a &lt; b &amp; c" in text


def test_long_quote_is_collapsed_and_cut():
    text = render(PullRequestCommented(REPO, f.pr(), f.pr_comment(body="x" * 1000)))
    assert "<blockquote expandable>" in text
    assert "…</blockquote>" in text


def test_opened_pull_request_shows_task_and_pings_reviewers():
    text = render(PullRequestOpened(REPO, f.pr(reviewers=("mentor", "architect"))), ("mentor",))
    assert text.startswith("🆕 <b>Новый PR</b> · #backend")
    assert "Задача #17653" in text
    assert "<code>feature/17653-image-search</code> → <code>main</code>" in text
    assert '🔔 <a href="https://github.com/architect">architect</a>, <a href="tg://user?id=1">Mentor</a>' in text


def test_draft_does_not_ping():
    text = render(PullRequestOpened(REPO, f.pr(draft=True, reviewers=("mentor",))), ("mentor",))
    assert "Черновик" in text and "🔔" not in text


def test_merged_reminds_author_about_redmine():
    text = render(PullRequestMerged(REPO, f.merged_pr()), ("student",))
    assert "🟣 <b>PR влит</b>" in text
    assert f"🔔 {PING_STUDENT}, переведи" in text and "Resolved" in text


def test_closed_without_merge():
    text = render(PullRequestClosed(REPO, f.pr(state="closed", closed_at="2026-10-02T00:00:00Z")))
    assert "без слияния" in text and "🔔" not in text


def test_failed_build_names_broken_steps_and_pings_pusher():
    event = BuildFinished(REPO, f.run(conclusion="failure", pull_requests=(12,)), (FailedJob("build", "Run tests"),))
    text = render(event, ("student",))
    assert text.startswith("🔴 <b>Сборка упала</b> · #backend")
    assert "💥 build › Run tests" in text
    assert f'<a href="{f.REPO_URL}/pull/12">PR #12</a>' in text
    assert "2 мин 13 с" in text
    assert f"🔔 {PING_STUDENT}, посмотри" in text


def test_successful_build_does_not_ping():
    text = render(BuildFinished(REPO, f.run()), ("student",))
    assert text.startswith("🟢 <b>Сборка прошла</b>")
    assert "tg://" not in text


def test_plural():
    assert [plural(k, "a", "b", "c") for k in (1, 2, 5, 11, 12, 21, 22, 25)] == list("abcccabc")


def test_codeowners_team_pings_its_members_except_author():
    project = replace(f.PROJECT, teams={"maintainers": ("Mentor", "student")})
    pr = f.pr(teams=("maintainers",))
    text = cards.render(PullRequestOpened(REPO, pr), f.view(("mentor", "student"), project))
    assert text.endswith('🔔 <a href="tg://user?id=1">Mentor</a> — ждём ревью')


def test_team_without_members_is_shown_as_link():
    text = render(ReviewRequested(REPO, f.pr(), ReviewRequests(teams=("maintainers",))))
    assert '🔔 <a href="https://github.com/orgs/dejaview-nsu/teams/maintainers">👥 maintainers</a>' in text


def test_person_with_username_is_mentioned_by_it():
    people = f.people()
    people.save(Person("student", 1, "Student", "student_tg"))
    view = View(people, str, f.PROJECT)
    text = cards.render(PullRequestMerged(REPO, f.merged_pr()), view)
    assert "🔔 @student_tg, переведи" in text


def test_task_done_status_comes_from_project():
    view = f.view(project=replace(f.PROJECT, task_done_status="Решена"))
    assert "в Решена со ссылкой" in cards.render(PullRequestMerged(REPO, f.merged_pr()), view)
