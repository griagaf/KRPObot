import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram.filters import CommandObject
from aiogram.types import Message

from bot.changelog import ChangelogService
from bot.github import GitHubError
from bot.telegram import changelog_view
from bot.telegram.handlers.common import HELP
from bot.telegram.period import parse_period
from bot.telegram.view import View

log = logging.getLogger(__name__)


async def show_changelog(
    message: Message, command: CommandObject, changelog: ChangelogService, view: View, timezone: ZoneInfo
) -> None:
    try:
        since, until = parse_period(command.args or "", datetime.now(timezone).date())
    except ValueError:
        await message.answer("Не понял период.\n\n" + HELP)
        return
    try:
        result = await changelog.build(since, until)
    except GitHubError:
        log.exception("Не удалось собрать changelog")
        await message.answer("GitHub не ответил, попробуй позже.")
        return
    for text in changelog_view.render(result, view):
        await message.answer(text)
