"""Шлёт в чат по примеру каждой карточки: посмотреть оформление без событий в GitHub и без CI.

    python -m bot.demo                 # в TELEGRAM_CHAT_ID, а если его нет — в чат, откуда первым напишут боту
    python -m bot.demo --login octocat # вы автор PR и адресат 🔔; с /link увидите настоящую отметку

Нужен только TELEGRAM_BOT_TOKEN. Основной бот на время демо остановите: Telegram отдаёт
сообщения только одному получателю.
"""

import argparse
import asyncio
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv

from bot import db
from bot.config import parse_chat_id
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
from bot.people import PeopleStore
from bot.telegram.handlers import COMMANDS
from bot.telegram.notifier import ChatNotifier, ChatTarget
from bot.telegram.policy import ChatPolicy
from bot.telegram.view import View

ORG = "dejaview-nsu"
REPO = "dejaview-backend"
REPO_URL = f"https://github.com/{ORG}/{REPO}"
MENTOR = User("mentor-demo")
NOW = datetime.now(UTC)


def sample_events(author: User) -> list[RepoEvent]:
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
        created_at=NOW,
        updated_at=NOW,
        closed_at=None,
        merged_at=None,
    )
    merged = replace(pr, is_open=False, closed_at=NOW, merged_at=NOW)
    code_comments = tuple(
        ReviewComment(i, 5, 12, path, body, MENTOR, f"{REPO_URL}/pull/12#discussion_r{i}", NOW)
        for i, path, body in [
            (1, "src/search/handler.cpp", "Лучше назвать find_by_frame"),
            (2, "src/api/routes.cpp", "Здесь нужен таймаут"),
        ]
    )

    def review(state: ReviewState, body: str) -> Review:
        return Review(5, state, body, MENTOR, f"{REPO_URL}/pull/12#pullrequestreview-5", NOW)

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
            started_at=NOW - timedelta(minutes=2, seconds=13),
            finished_at=NOW,
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
            PullRequestComment(9, 12, "Поправил, посмотри ещё раз", author, f"{REPO_URL}/pull/12", NOW),
        ),
        ReviewSubmitted(REPO, pr, review(ReviewState.APPROVED, "Отлично, только поправь нейминг"), code_comments),
        PullRequestMerged(REPO, merged),
    ]


async def wait_for_chat(bot: Bot) -> ChatTarget:
    print("TELEGRAM_CHAT_ID не задан. Напишите боту что угодно в личку или в нужную тему группы…")
    offset = None
    while True:
        for update in await bot.get_updates(offset=offset, timeout=50):
            offset = update.update_id + 1
            if message := update.message:
                thread = message.message_thread_id if message.is_topic_message else None
                print(f"TELEGRAM_CHAT_ID={message.chat.id}" + (f"\nTELEGRAM_THREAD_ID={thread}" if thread else ""))
                await bot.get_updates(offset=offset, timeout=0)  # подтверждаем, чтобы бот не увидел его снова
                return ChatTarget(message.chat.id, thread)


async def main(login: str) -> None:
    load_dotenv()
    bot = Bot(
        os.environ["TELEGRAM_BOT_TOKEN"],
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True),
    )
    connection = db.connect(os.getenv("DB_PATH", "bot.sqlite3"))
    try:
        await bot.set_my_commands(COMMANDS)
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        thread_id = os.getenv("TELEGRAM_THREAD_ID")
        target = (
            ChatTarget(parse_chat_id(chat_id), int(thread_id) if thread_id else None)
            if chat_id
            else await wait_for_chat(bot)
        )
        redmine_url = os.getenv("REDMINE_URL", "https://ai.nsu.ru").rstrip("/")
        view = View(PeopleStore(connection), lambda task: f"{redmine_url}/issues/{task}", ORG)
        notifier = ChatNotifier(bot, target, view, ChatPolicy(notify_build_success=True))
        events = sample_events(User(login))
        for event in events:
            await notifier.handle(event)
        print(f"Готово: отправлено {len(events)} карточек")
    finally:
        await bot.session.close()
        connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--login", default="student-demo", help="GitHub-логин автора PR в примерах")
    asyncio.run(main(parser.parse_args().login))
