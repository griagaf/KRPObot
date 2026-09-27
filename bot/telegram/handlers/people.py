from aiogram.filters import CommandObject
from aiogram.types import Message

from bot.github import GitHubError
from bot.people import InvalidLoginError, LoginTakenError, PeopleService, UnknownLoginError
from bot.telegram.markup import esc
from bot.telegram.view import View


async def link_account(message: Message, command: CommandObject, people: PeopleService, view: View) -> None:
    if message.from_user is None:
        await message.answer("Не вижу, кто пишет. Напиши не от имени группы.")
        return
    login = command.args or ""
    try:
        user = message.from_user
        person = await people.link(login, user.id, user.full_name, user.username)
    except InvalidLoginError:
        await message.answer("Напиши свой логин на GitHub: <code>/link octocat</code>")
    except UnknownLoginError:
        await message.answer(f"На GitHub нет пользователя <code>{esc(login)}</code>.")
    except LoginTakenError as err:
        await message.answer(
            f"{view.github_profile(err.owner.github_login)} уже связан с {esc(err.owner.tg_name)}. "
            "Если это ошибка, пусть там сделают /unlink."
        )
    except GitHubError:
        await message.answer("GitHub не ответил, попробуй позже.")
    else:
        text = (
            f"🔗 {view.github_profile(person.github_login)} ↔ {view.mention(person.github_login)}\n"
            "Теперь буду отмечать тебя в ревью, в том числе когда его просят у твоей команды, "
            "в комментариях к твоим PR и в упавших сборках."
        )
        if person.tg_username is None:
            # отметка без @username доходит, только если человек писал боту в личку
            text += (
                "\n\n⚠️ У тебя нет имени пользователя в Telegram, отметка может не прийти. "
                "Задай его в настройках Telegram и сделай /link ещё раз."
            )
        await message.answer(text)


async def unlink_account(message: Message, people: PeopleService, view: View) -> None:
    person = people.unlink(message.from_user.id) if message.from_user else None
    if person is None:
        await message.answer("Ты ни с кем не связан.")
    else:
        await message.answer(f"Отвязал {view.github_profile(person.github_login)}.")


async def list_people(message: Message, people: PeopleService, view: View) -> None:
    linked = people.all()
    if not linked:
        await message.answer("Пока никто не связан. Начни с /link <i>github-логин</i>.")
        return
    # Имена без упоминаний: список не должен пинговать всю команду.
    lines = [f"👥 <b>GitHub ↔ Telegram</b> · {len(linked)}", ""]
    lines += [f"• {view.github_profile(p.github_login)} — {esc(p.tg_name)}" for p in linked]
    await message.answer("\n".join(lines))
