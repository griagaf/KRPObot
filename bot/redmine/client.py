import asyncio
import logging
from types import TracebackType
from typing import Self

import httpx

log = logging.getLogger(__name__)


class RedmineClient:
    """Темы задач для changelog. Без API-ключа тем нет, остаются ссылки на задачи."""

    def __init__(self, url: str, api_key: str | None, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._url = url
        self._api_key = api_key
        headers = {"X-Redmine-API-Key": api_key} if api_key else {}
        self._http = httpx.AsyncClient(base_url=url, timeout=15, headers=headers, transport=transport)
        self._subjects: dict[int, str] = {}

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        await self._http.aclose()

    def issue_url(self, issue_id: int) -> str:
        return f"{self._url}/issues/{issue_id}"

    async def subject(self, issue_id: int) -> str | None:
        """Тема задачи; None, если её не удалось получить: changelog без темы лучше, чем без changelog."""
        if not self._api_key:
            return None
        if issue_id not in self._subjects:
            try:
                response = await self._http.get(f"/issues/{issue_id}.json")
                response.raise_for_status()
            except httpx.HTTPError as err:
                log.warning("Redmine: не удалось получить #%s: %r", issue_id, err)
                return None
            self._subjects[issue_id] = response.json()["issue"]["subject"]
        return self._subjects[issue_id]

    async def subjects(self, issue_ids: set[int]) -> dict[int, str]:
        ids = sorted(issue_ids)
        found = await asyncio.gather(*(self.subject(i) for i in ids))
        return {i: s for i, s in zip(ids, found, strict=True) if s}
