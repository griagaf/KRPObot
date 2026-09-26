from aiogram.types import Message

HELP = (
    "Слежу за PR и сборками в GitHub и пишу о них в чат.\n\n"
    "<b>Люди</b>\n"
    "/link <i>github-логин</i> — связать свой Telegram с GitHub, чтобы я отмечал тебя\n"
    "/unlink — отвязать\n"
    "/people — кто с кем связан\n\n"
    "<b>Changelog</b>\n"
    "/changelog — за последние 14 дней\n"
    "/changelog 7d — за последние 7 дней\n"
    "/changelog 29.09 — с 29.09 по сегодня\n"
    "/changelog 29.09 12.10 — за период\n\n"
    "/chatid — id этого чата и темы, для настройки"
)


async def show_help(message: Message) -> None:
    await message.answer(HELP)


async def show_chat_id(message: Message) -> None:
    text = f"TELEGRAM_CHAT_ID=<code>{message.chat.id}</code>"
    if message.is_topic_message:
        text += f"\nTELEGRAM_THREAD_ID=<code>{message.message_thread_id}</code>"
    await message.answer(text)
