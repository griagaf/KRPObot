from bot.changelog import Changelog, ChangelogEntry
from bot.telegram.markup import esc, link, split_messages
from bot.telegram.view import View

SECTION_TITLES = {
    "feat": "✨ Новое",
    "fix": "🐛 Исправления",
    "perf": "⚡ Производительность",
    "refactor": "♻️ Рефакторинг",
    "docs": "📝 Документация",
    "test": "🧪 Тесты",
    "other": "🔧 Прочее",
}


def render(changelog: Changelog, view: View) -> list[str]:
    """Changelog одним или несколькими сообщениями, если не влез в лимит Telegram."""
    header = f"📋 <b>Changelog</b> · {changelog.since:%d.%m.%Y} – {changelog.until:%d.%m.%Y}"
    sections = changelog.sections()
    if not sections:
        return [f"{header}\n\nЗа этот период ничего не влито."]

    lines = [header]
    for kind, entries in sections:
        lines += ["", f"<b>{SECTION_TITLES[kind]}</b>", *(_entry(e, view) for e in entries)]
    return split_messages(lines)


def _entry(entry: ChangelogEntry, view: View) -> str:
    pr = link(entry.pr.url, f"#{entry.pr.number}")
    line = f"• <b>{esc(view.repo(entry.repo))}</b>: {esc(entry.change.text)} — {pr}"
    if entry.task:
        line += f" · {view.task(entry.task)}"
        if entry.task_subject:
            line += f" {esc(entry.task_subject)}"
    return line
