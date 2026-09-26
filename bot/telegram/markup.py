"""Кирпичики Telegram HTML."""

import html
import re

MESSAGE_LIMIT = 4096
QUOTE_LIMIT = 600
QUOTE_COLLAPSE_FROM = 200


def esc(text: str) -> str:
    return html.escape(text, quote=False)


def link(url: str, text: str) -> str:
    """text — уже готовый HTML."""
    return f'<a href="{html.escape(url)}">{text}</a>'


def hashtag(text: str) -> str:
    return "#" + re.sub(r"\W", "_", text)


def code(text: str) -> str:
    return f"<code>{esc(text)}</code>"


def quote(body: str) -> str:
    """Цитата; длинная сворачивается, чтобы не растягивать ленту."""
    text = re.sub(r"\n{3,}", "\n\n", body.strip())
    if not text:
        return ""
    if len(text) > QUOTE_LIMIT:
        text = text[:QUOTE_LIMIT].rstrip() + "…"
    collapsed = len(text) > QUOTE_COLLAPSE_FROM or text.count("\n") > 3
    return f"<blockquote{' expandable' if collapsed else ''}>{esc(text)}</blockquote>"


def plural(n: int, one: str, few: str, many: str) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def card(*blocks: str | list[str]) -> str:
    """Блоки через пустую строку, строки блока подряд; пустое выбрасывается."""
    parts = []
    for block in blocks:
        text = "\n".join(line for line in block if line) if isinstance(block, list) else block
        if text:
            parts.append(text)
    return "\n\n".join(parts)


def split_messages(lines: list[str], limit: int = MESSAGE_LIMIT) -> list[str]:
    """Режет по строкам на сообщения не длиннее лимита Telegram."""
    chunks: list[str] = []
    current = ""
    for line in lines:
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > limit and current:
            chunks.append(current)
            candidate = line
        current = candidate
    return [*chunks, current] if current else chunks
