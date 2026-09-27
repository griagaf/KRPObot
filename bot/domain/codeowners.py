"""CODEOWNERS: кто владеет какими файлами репозитория.

Шаблоны как в .gitignore, но по правилам GitHub (docs.github.com, «About code owners»), а не git:
- без / в начале или середине шаблон ищется на любой глубине: `*.js`, `apps/`;
- с / в начале или середине — от корня: `/docs/`, `docs/*`;
- `*` и `?` не переходят через /, `**` переходит;
- шаблон-папка и шаблон с обычным именем в конце относятся и ко всему внутри, а `docs/*` — только к
  файлам прямо в docs, не глубже: здесь GitHub расходится с git;
- `!` и `[ ]` GitHub не поддерживает, такие правила он пропускает — и мы тоже.
Для файла решает последнее подходящее правило, даже если владельцев в нём нет.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass

from bot.domain.models import ReviewRequests

WILDCARDS = frozenset("*?")


@dataclass(frozen=True)
class Rule:
    pattern: re.Pattern[str]
    owners: ReviewRequests


@dataclass(frozen=True)
class CodeOwners:
    rules: tuple[Rule, ...]

    @classmethod
    def parse(cls, text: str) -> "CodeOwners":
        rules = []
        for line in text.splitlines():
            parts = line.split()
            if not parts or parts[0].startswith("#") or parts[0].startswith("!") or "[" in parts[0]:
                continue
            owners = []
            for token in parts[1:]:
                if token.startswith("#"):  # комментарий до конца строки
                    break
                owners.append(token)
            rules.append(Rule(compile_pattern(parts[0]), _owners(owners)))
        return cls(tuple(rules))

    def owners(self, paths: Iterable[str]) -> ReviewRequests:
        """Владельцы всех перечисленных файлов вместе."""
        users: dict[str, None] = {}
        teams: dict[str, None] = {}
        for path in paths:
            rule = next((r for r in reversed(self.rules) if r.pattern.fullmatch(path)), None)
            if rule is not None:
                users.update(dict.fromkeys(rule.owners.users))
                teams.update(dict.fromkeys(rule.owners.teams))
        return ReviewRequests(tuple(users), tuple(teams))


def compile_pattern(pattern: str) -> re.Pattern[str]:
    pattern = pattern.removeprefix("\\")  # \#file: # в начале экранируют, чтобы это был не комментарий
    anchored = "/" in pattern.rstrip("/")
    directory = pattern.endswith("/")
    segments = pattern.strip("/").split("/")

    regex = "" if anchored else "(?:.*/)?"
    for i, segment in enumerate(segments):
        last = i == len(segments) - 1
        if segment == "**":
            regex += ".*" if last else "(?:.*/)?"
        else:
            regex += _segment(segment) + ("" if last else "/")

    tail = segments[-1]
    if directory:
        regex += "/.*"
    elif tail != "**" and not WILDCARDS & set(tail):
        regex += "(?:/.*)?"  # обычное имя может оказаться папкой
    return re.compile(regex)


def _segment(segment: str) -> str:
    return "".join("[^/]*" if c == "*" else "[^/]" if c == "?" else re.escape(c) for c in segment)


def _owners(tokens: list[str]) -> ReviewRequests:
    """@login — человек, @org/team — команда; почту на GitHub-логин не сопоставить, её пропускаем."""
    users = tuple(t[1:] for t in tokens if t.startswith("@") and "/" not in t)
    teams = tuple(t.rsplit("/", 1)[1].lower() for t in tokens if t.startswith("@") and "/" in t)
    return ReviewRequests(users, teams)
