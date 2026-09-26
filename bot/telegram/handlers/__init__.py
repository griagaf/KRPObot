"""Команды бота. Зависимости (people, changelog, view, timezone) приходят из workflow_data диспетчера."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import BotCommand

from bot.telegram.handlers import changelog, common, people

COMMANDS = [
    BotCommand(command="changelog", description="Изменения за период, по умолчанию 14 дней"),
    BotCommand(command="link", description="Связать Telegram с GitHub-логином"),
    BotCommand(command="unlink", description="Отвязать GitHub"),
    BotCommand(command="people", description="Кто с кем связан"),
    BotCommand(command="help", description="Что я умею"),
]


def build_router() -> Router:
    router = Router(name="commands")
    router.message.register(common.show_help, Command("start", "help"))
    router.message.register(common.show_chat_id, Command("chatid"))
    router.message.register(people.link_account, Command("link"))
    router.message.register(people.unlink_account, Command("unlink"))
    router.message.register(people.list_people, Command("people"))
    router.message.register(changelog.show_changelog, Command("changelog"))
    return router


__all__ = ["COMMANDS", "build_router"]
