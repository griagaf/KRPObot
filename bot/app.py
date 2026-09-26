"""Точка сборки: создаёт зависимости и запускает наблюдатель вместе с приёмом команд."""

import asyncio
import contextlib
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot import db
from bot.changelog import ChangelogService
from bot.config import Settings
from bot.github import GitHubClient
from bot.people import PeopleService, PeopleStore
from bot.redmine import RedmineClient
from bot.telegram.handlers import COMMANDS, build_router
from bot.telegram.notifier import ChatNotifier, ChatTarget
from bot.telegram.policy import ChatPolicy
from bot.telegram.view import View
from bot.watcher import RepoScanner, Watcher, WatchState

log = logging.getLogger(__name__)


async def run(settings: Settings) -> None:
    connection = db.connect(settings.db_path)
    bot = Bot(
        settings.telegram_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True),
    )
    try:
        # До обращений к GitHub: меню команд появится, даже если GitHub недоступен.
        await bot.set_my_commands(COMMANDS)
        async with (
            GitHubClient(settings.github_token, settings.github_org) as github,
            RedmineClient(settings.redmine_url, settings.redmine_api_key) as redmine,
        ):
            repos = settings.repos or tuple(await github.org_repos())
            people = PeopleStore(connection)
            view = View(people, redmine.issue_url, settings.github_org)
            state = WatchState(connection)
            notifier = ChatNotifier(
                bot, ChatTarget(settings.chat_id, settings.thread_id), view, ChatPolicy(settings.notify_build_success)
            )
            watcher = Watcher(RepoScanner(github, state), state, repos, [notifier], interval=settings.poll_interval)

            dispatcher = Dispatcher(
                people=PeopleService(people, github),
                changelog=ChangelogService(github, redmine, repos, settings.timezone),
                view=view,
                timezone=settings.timezone,
            )
            dispatcher.include_router(build_router())

            log.info("Слежу за репозиториями: %s", ", ".join(repos))
            watch_task = asyncio.create_task(watcher.run(), name="watcher")
            try:
                await dispatcher.start_polling(bot)
            finally:
                watch_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await watch_task
    finally:
        await bot.session.close()
        connection.close()
