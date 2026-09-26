import asyncio
import logging
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Protocol

from bot.domain.events import RepoEvent
from bot.watcher.scanner import RepoScanner
from bot.watcher.state import WatchState

log = logging.getLogger(__name__)


class EventHandler(Protocol):
    async def handle(self, event: RepoEvent) -> None:
        """Реакция на событие. Исключение означает «повторить позже»: событие придёт снова."""


class Watcher:
    """Раз в interval секунд сканирует репозитории и раздаёт новые события обработчикам.

    Первый проход по репозиторию только запоминает состояние. Дальше публикуются лишь события,
    случившиеся после начала наблюдения: давний PR, который снова обновили, не всплывёт как новый.
    """

    def __init__(
        self,
        scanner: RepoScanner,
        state: WatchState,
        repos: Sequence[str],
        handlers: Sequence[EventHandler],
        *,
        interval: int,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._scanner = scanner
        self._state = state
        self._repos = repos
        self._handlers = handlers
        self._interval = interval
        self._clock = clock

    async def run(self) -> None:
        while True:
            for repo in self._repos:
                try:
                    await self.poll(repo)
                except Exception:
                    # Граница цикла: сбой одного репозитория не должен останавливать наблюдение за остальными.
                    log.exception("Опрос %s не удался, повторю через %s с", repo, self._interval)
            await asyncio.sleep(self._interval)

    async def poll(self, repo: str) -> None:
        since = self._state.watching_since(repo)
        scan = await self._scanner.scan(repo, fetch_details=since is not None)
        for event in scan.events:
            if since is not None and event.occurred_at >= since:
                for handler in self._handlers:
                    await handler.handle(event)
            self._state.mark_seen(event.keys)
        # Только после обработки: если она упала, изменения этих PR перечитаются в следующий раз.
        self._state.remember_pulls(scan.pulls)
        if since is None:
            self._state.start_watching(repo, self._clock())
