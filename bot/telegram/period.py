"""Период из аргументов /changelog."""

import re
from datetime import date, datetime, timedelta

DEFAULT_DAYS = 14  # длина спринта
LAST_DAYS = re.compile(r"(\d+)d")


def parse_date(value: str, today: date) -> date:
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    return datetime.strptime(f"{value}.{today.year}", "%d.%m.%Y").date()


def parse_period(args: str, today: date) -> tuple[date, date]:
    """'' — последние 14 дней; '7d'; '29.09' — с даты по сегодня; '29.09 12.10' — интервал.

    ValueError, если разобрать не удалось.
    """
    parts = args.split()
    if not parts:
        return today - timedelta(days=DEFAULT_DAYS - 1), today
    if len(parts) == 1 and (days := LAST_DAYS.fullmatch(parts[0])):
        return today - timedelta(days=int(days[1]) - 1), today
    if len(parts) > 2:
        raise ValueError("слишком много аргументов")
    since = parse_date(parts[0], today)
    until = parse_date(parts[1], today) if len(parts) == 2 else today
    if since > until:
        raise ValueError("начало периода позже конца")
    return since, until
