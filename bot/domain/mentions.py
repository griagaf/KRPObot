"""Кого отметили через @ в тексте на GitHub: @login или команду @org/team.

Как и GitHub, не считаем упоминаниями @ в коде и в почте. Цитаты тоже пропускаем: «> @alice писала»
пересказывает чужое сообщение, а не зовёт alice.
"""

import re
from dataclasses import dataclass

CODE_BLOCK = re.compile(r"^ {0,3}(`{3,}|~{3,}).*?^ {0,3}\1", re.MULTILINE | re.DOTALL)
INLINE_CODE = re.compile(r"(`+).+?\1", re.DOTALL)
QUOTE = re.compile(r"^ {0,3}>.*$", re.MULTILINE)
# логин GitHub: буквы, цифры и одиночные дефисы, не длиннее 39; перед @ не буква, иначе это почта
MENTION = re.compile(r"(?<![\w@])@([A-Za-z0-9](?:-?[A-Za-z0-9]){0,38})(?:/([A-Za-z0-9._-]+))?(?![\w-])")


@dataclass(frozen=True)
class Mentions:
    users: tuple[str, ...] = ()
    teams: tuple[str, ...] = ()  # без организации, в нижнем регистре, как slug в API


def mentions(*texts: str) -> Mentions:
    users: dict[str, str] = {}
    teams: dict[str, None] = {}
    for text in texts:
        text = QUOTE.sub("", INLINE_CODE.sub("", CODE_BLOCK.sub("", text)))
        for login, team in MENTION.findall(text):
            if team:
                teams[team.lower().rstrip(".")] = None
            else:
                users.setdefault(login.lower(), login)  # логины GitHub не зависят от регистра
    return Mentions(tuple(users.values()), tuple(teams))
