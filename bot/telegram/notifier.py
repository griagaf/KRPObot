import asyncio
import logging
from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter

from bot.domain.events import RepoEvent
from bot.telegram import cards
from bot.telegram.policy import ChatPolicy
from bot.telegram.view import View

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChatTarget:
    chat_id: int | str
    thread_id: int | None = None


class ChatNotifier:
    """Публикует карточки событий в тему группы."""

    def __init__(self, bot: Bot, target: ChatTarget, view: View, policy: ChatPolicy) -> None:
        self._bot = bot
        self._target = target
        self._view = view
        self._policy = policy

    async def handle(self, event: RepoEvent) -> None:
        if self._policy.allows(event):
            await self.send(cards.render(event, self._view))

    async def send(self, text: str) -> None:
        """Сетевые сбои пробрасываются: наблюдатель повторит событие. Отказ Telegram — нет:
        повтор того же сообщения снова упадёт и навсегда застопорит репозиторий."""
        while True:
            try:
                await self._bot.send_message(self._target.chat_id, text, message_thread_id=self._target.thread_id)
                return
            except TelegramRetryAfter as err:
                await asyncio.sleep(err.retry_after)
            except TelegramBadRequest:
                log.exception("Telegram отклонил сообщение, пропускаю:\n%s", text)
                return
