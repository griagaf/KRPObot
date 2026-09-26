"""Карточки событий: заголовок с хэштегом репозитория, PR, детали, цитата и 🔔 тем, кому реагировать."""

from collections.abc import Sequence
from datetime import timedelta

from bot.domain.conventions import task_id
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
)
from bot.domain.models import PullRequest, ReviewComment, ReviewState
from bot.telegram.markup import card, code, esc, link, plural, quote
from bot.telegram.view import View

REVIEW_TITLES: dict[str, str] = {
    ReviewState.APPROVED: "✅ <b>Одобрено</b>",
    ReviewState.CHANGES_REQUESTED: "🛠 <b>Нужны правки</b>",
    ReviewState.COMMENTED: "💬 <b>Ревью</b>",
}
MAX_FILES_SHOWN = 3
MAX_FAILED_JOBS_SHOWN = 10


def render(event: RepoEvent, view: View) -> str:
    match event:
        case PullRequestOpened():
            return _pull_request_opened(event, view)
        case ReviewRequested():
            return _review_requested(event, view)
        case PullRequestMerged():
            return _pull_request_merged(event, view)
        case PullRequestClosed():
            return _pull_request_closed(event, view)
        case ReviewSubmitted():
            return _review_submitted(event, view)
        case CodeCommented():
            return _code_commented(event, view)
        case PullRequestCommented():
            return _pull_request_commented(event, view)
        case BuildFinished():
            return _build_finished(event, view)
    raise TypeError(f"Нет карточки для {type(event).__name__}")


def _header(event: RepoEvent, view: View, title: str) -> str:
    return f"{title} · {view.repo_tag(event.repo)}"


def _pr_title(pr: PullRequest) -> str:
    return "<b>" + link(pr.url, f"#{pr.number} · {esc(pr.title)}") + "</b>"


def _branches(pr: PullRequest) -> str:
    return f"🌿 {code(pr.head)} → {code(pr.base)}"


def _task(pr: PullRequest, view: View) -> str:
    task = task_id(pr)
    return f"📌 {view.task(task, f'Задача #{task}')}" if task else ""


def _bell(view: View, logins: Sequence[str], *, actor: str | None = None, suffix: str = "") -> str:
    """🔔 с упоминаниями. Автора действия не отмечаем: он и так в курсе."""
    targets = [login for login in dict.fromkeys(logins) if login.lower() != (actor or "").lower()]
    return f"🔔 {view.mentions(targets)}{suffix}" if targets else ""


def _comments_count(n: int) -> str:
    return f"{n} {plural(n, 'комментарий', 'комментария', 'комментариев')}"


def _files(comments: Sequence[ReviewComment]) -> str:
    paths = list(dict.fromkeys(c.path for c in comments if c.path))
    if not paths:
        return ""
    shown = ", ".join(code(p) for p in paths[:MAX_FILES_SHOWN])
    rest = len(paths) - MAX_FILES_SHOWN
    return f"📄 {shown}" + (f" и ещё {rest}" if rest > 0 else "")


def _duration(value: timedelta) -> str:
    minutes, seconds = divmod(int(value.total_seconds()), 60)
    return f"{minutes} мин {seconds} с" if minutes else f"{seconds} с"


def _pull_request_opened(event: PullRequestOpened, view: View) -> str:
    pr = event.pr
    title = "📝 <b>Черновик PR</b>" if pr.is_draft else "🆕 <b>Новый PR</b>"
    reviewers = () if pr.is_draft else pr.requested_reviewers
    return card(
        [_header(event, view, title), _pr_title(pr)],
        [f"👤 {view.name(pr.author.login)}", _branches(pr), _task(pr, view)],
        _bell(view, reviewers, actor=pr.author.login, suffix=" — ждём ревью"),
    )


def _review_requested(event: ReviewRequested, view: View) -> str:
    return card(
        [_header(event, view, "👀 <b>Запрошено ревью</b>"), _pr_title(event.pr)],
        [f"👤 {view.name(event.pr.author.login)}", _branches(event.pr)],
        _bell(view, event.reviewers),
    )


def _pull_request_merged(event: PullRequestMerged, view: View) -> str:
    pr = event.pr
    task = task_id(pr)
    reminder = (
        f"🔔 {view.mention(pr.author.login)}, переведи {view.task(task)} в Resolved со ссылкой на PR" if task else ""
    )
    return card(
        [_header(event, view, "🟣 <b>PR влит</b>"), _pr_title(pr)],
        [f"👤 {view.name(pr.author.login)}", _branches(pr)],
        reminder,
    )


def _pull_request_closed(event: PullRequestClosed, view: View) -> str:
    return card(
        [_header(event, view, "⚫ <b>PR закрыт без слияния</b>"), _pr_title(event.pr)],
        f"👤 {view.name(event.pr.author.login)}",
    )


def _review_submitted(event: ReviewSubmitted, view: View) -> str:
    """Ревью вместе с его комментариями к коду: одна карточка вместо N."""
    review, comments = event.review, event.comments
    body = review.body.strip()
    if review.state == ReviewState.COMMENTED and not body:
        title = "💬 <b>Комментарий к коду</b>" if len(comments) == 1 else "💬 <b>Комментарии к коду</b>"
    else:
        title = REVIEW_TITLES.get(review.state, "💬 <b>Ревью</b>")

    details = [f"👤 {view.name(review.author.login)}"]
    if comments:
        details += [f"💬 {link(review.url, _comments_count(len(comments)) + ' к коду')}", _files(comments)]
    return card(
        [_header(event, view, title), _pr_title(event.pr)],
        details,
        quote(body or (comments[0].body if comments else "")),
        _bell(view, [event.pr.author.login], actor=review.author.login),
    )


def _code_commented(event: CodeCommented, view: View) -> str:
    first = event.comments[0]
    count = f" · {_comments_count(len(event.comments))}" if len(event.comments) > 1 else ""
    return card(
        [_header(event, view, "💬 <b>Комментарий к коду</b>"), _pr_title(event.pr)],
        [f"👤 {view.name(first.author.login)}{count} · {link(first.url, 'открыть →')}", _files(event.comments)],
        quote(first.body),
        _bell(view, [event.pr.author.login], actor=first.author.login),
    )


def _pull_request_commented(event: PullRequestCommented, view: View) -> str:
    comment = event.comment
    return card(
        [_header(event, view, "💬 <b>Комментарий</b>"), _pr_title(event.pr)],
        f"👤 {view.name(comment.author.login)} · {link(comment.url, 'открыть →')}",
        quote(comment.body),
        _bell(view, [event.pr.author.login], actor=comment.author.login),
    )


def _build_finished(event: BuildFinished, view: View) -> str:
    run = event.run
    workflow = "<b>" + link(run.url, f"{esc(run.workflow)} #{run.number}") + "</b>"
    pr = link(run.pr_url(run.pr_numbers[0]), f"PR #{run.pr_numbers[0]}") if run.pr_numbers else ""

    if not run.failed:
        return card(
            [
                _header(event, view, "🟢 <b>Сборка прошла</b>"),
                f"{workflow} · {code(run.branch)}",
                " · ".join(part for part in (f"📝 {esc(run.title)}", pr) if part),
                f"👤 {view.name(run.actor.login)} · ⏱ {_duration(run.duration)}",
            ]
        )

    failed = [f"💥 {esc(job.name)}" + (f" › {esc(job.step)}" if job.step else "") for job in event.failed_jobs]
    if len(failed) > MAX_FAILED_JOBS_SHOWN:
        failed = [*failed[:MAX_FAILED_JOBS_SHOWN], f"… и ещё {len(failed) - MAX_FAILED_JOBS_SHOWN}"]
    return card(
        [
            _header(event, view, "🔴 <b>Сборка упала</b>"),
            f"{workflow} · {code(run.branch)}",
            f"📝 {esc(run.title)}",
            f"🔗 {pr}" if pr else "",
        ],
        failed,
        f"⏱ {_duration(run.duration)}",
        _bell(view, [run.actor.login], suffix=", посмотри, что сломалось"),
    )
