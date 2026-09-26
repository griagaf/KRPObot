"""Соглашения команды из регламента: ветки feature/17XXX-name и conventional commits в заголовках PR."""

import re
from dataclasses import dataclass

from bot.domain.models import PullRequest

TASK_IN_BRANCH = re.compile(r"^[\w-]+/(\d{4,6})\b")
TASK_IN_TEXT = re.compile(r"(?:#|/issues/)(\d{4,6})\b")
CONVENTIONAL_TITLE = re.compile(r"^(?P<kind>[a-zA-Z]+)(?:\((?P<scope>[^)]*)\))?!?:\s*(?P<text>.+)$")

CHANGE_KINDS = ("feat", "fix", "perf", "refactor", "docs", "test")
OTHER_KIND = "other"


@dataclass(frozen=True)
class ChangeTitle:
    kind: str
    text: str

    @classmethod
    def parse(cls, title: str) -> "ChangeTitle":
        title = title.strip()
        match = CONVENTIONAL_TITLE.match(title)
        if match is None:
            return cls(OTHER_KIND, title)
        kind = match["kind"].lower()
        text = f"{match['scope']}: {match['text']}" if match["scope"] else match["text"]
        return cls(kind if kind in CHANGE_KINDS else OTHER_KIND, text)


def task_id(pr: PullRequest) -> int | None:
    """Номер задачи Redmine: из ветки, иначе из заголовка или описания PR."""
    if match := TASK_IN_BRANCH.match(pr.head):
        return int(match[1])
    for text in (pr.title, pr.body):
        if match := TASK_IN_TEXT.search(text):
            return int(match[1])
    return None
