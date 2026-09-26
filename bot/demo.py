"""Демо-режим (changelog-bot --demo): команда /demo присылает по примеру каждой карточки.

Помогает посмотреть оформление без событий в GitHub и без CI.
"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import BotCommand, Message

from bot.domain.events import (
    BuildFinished,
    CodeCommented,
    PullRequestCommented,
    PullRequestMerged,
    PullRequestOpened,
    RepoEvent,
    ReviewRequested,
    ReviewSubmitted,
)
from bot.domain.models import (
    FailedJob,
    PullRequest,
    PullRequestComment,
    Review,
    ReviewComment,
    ReviewState,
    User,
    WorkflowRun,
)
from bot.people import PeopleService
from bot.telegram import handlers
from bot.telegram.handlers.common import HELP
from bot.telegram.notifier import ChatNotifier, ChatTarget
from bot.telegram.policy import ChatPolicy
from bot.telegram.view import View

COMMANDS = [BotCommand(command="demo", description="Примеры всех карточек уведомлений"), *handlers.COMMANDS]
DEMO_HELP = (
    "🧪 <b>Демо-режим</b>: за репозиториями не слежу.\n"
    "/demo — прислать примеры всех карточек. Если сделать /link, автором PR в примерах будешь ты.\n\n" + HELP
)

REPO = "dejaview-backend"
REPO_URL = f"https://github.com/dejaview-nsu/{REPO}"
DEFAULT_AUTHOR = "student-demo"
MENTOR = User("mentor-demo")


def build_router() -> Router:
    router = Router(name="demo")
    router.message.register(show_demo_help, Command("start", "help"))
    router.message.register(send_demo_cards, Command("demo"))
    return router


async def show_demo_help(message: Message) -> None:
    await message.answer(DEMO_HELP)


async def send_demo_cards(message: Message, bot: Bot, people: PeopleService, view: View) -> None:
    linked = people.find_by_telegram(message.from_user.id) if message.from_user else None
    author = User(linked.github_login if linked else DEFAULT_AUTHOR)
    thread_id = message.message_thread_id if message.is_topic_message else None
    notifier = ChatNotifier(bot, ChatTarget(message.chat.id, thread_id), view, ChatPolicy(notify_build_success=True))
    for event in sample_events(author):
        await notifier.handle(event)


def sample_events(author: User) -> list[RepoEvent]:
    now = datetime.now(UTC)
    pr = PullRequest(
        id=1,
        number=12,
        title="feat: API поиска по изображению",
        body="",
        url=f"{REPO_URL}/pull/12",
        author=author,
        head="feature/17653-image-search",
        base="main",
        is_open=True,
        is_draft=False,
        requested_reviewers=(MENTOR.login,),
        created_at=now,
        updated_at=now,
        closed_at=None,
        merged_at=None,
    )
    merged = replace(pr, is_open=False, closed_at=now, merged_at=now)
    code_comments = tuple(
        ReviewComment(i, 5, 12, path, body, MENTOR, f"{REPO_URL}/pull/12#discussion_r{i}", now)
        for i, path, body in [
            (1, "src/search/handler.cpp", "Лучше назвать find_by_frame"),
            (2, "src/api/routes.cpp", "Здесь нужен таймаут"),
        ]
    )

    def review(state: ReviewState, body: str) -> Review:
        return Review(5, state, body, MENTOR, f"{REPO_URL}/pull/12#pullrequestreview-5", now)

    def run(conclusion: str, number: int) -> WorkflowRun:
        return WorkflowRun(
            id=number,
            attempt=1,
            workflow="CI",
            number=number,
            conclusion=conclusion,
            branch=pr.head,
            title=pr.title,
            url=f"{REPO_URL}/actions",
            repo_url=REPO_URL,
            actor=author,
            pr_numbers=(12,),
            started_at=now - timedelta(minutes=2, seconds=13),
            finished_at=now,
        )

    return [
        PullRequestOpened(REPO, pr),
        ReviewRequested(REPO, pr, ("architect-demo",)),
        BuildFinished(REPO, run("failure", 57), (FailedJob("build", "Run tests"), FailedJob("lint", "clang-format"))),
        BuildFinished(REPO, run("success", 58)),
        ReviewSubmitted(
            REPO,
            pr,
            review(
                ReviewState.CHANGES_REQUESTED,
                "Нет тестов на пустой кадр и на кадр больше 10 МБ. Добавь оба случая и проверь, что ошибка "
                "возвращается в формате из OpenAPI. Ещё: эмбеддинг считается синхронно в обработчике запроса, "
                "при 20 параллельных запросах это упрётся в ML-сервис. Вынеси в очередь или добавь таймаут.",
            ),
            (),
        ),
        CodeCommented(REPO, pr, code_comments[:1]),
        PullRequestCommented(
            REPO,
            pr,
            PullRequestComment(9, 12, "Поправил, посмотри ещё раз", author, f"{REPO_URL}/pull/12", now),
        ),
        ReviewSubmitted(REPO, pr, review(ReviewState.APPROVED, "Отлично, только поправь нейминг"), code_comments),
        PullRequestMerged(REPO, merged),
    ]
