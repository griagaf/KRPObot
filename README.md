# changelog_bot

Telegram-бот для DejaView. Пишет в тему общей группы о событиях в репозиториях
[dejaview-nsu](https://github.com/dejaview-nsu) и собирает changelog по команде.

**Уведомления**

| Событие | Карточка | Кого отмечает 🔔 |
|---|---|---|
| Сборка упала | 🔴 ветка, PR, упавший job и шаг, длительность | того, кто запушил |
| Сборка прошла | 🟢 компактно, в одну карточку | никого |
| Новый PR | 🆕 ветки, задача Redmine | ревьюеров |
| Запрошено ревью | 👀 | новых ревьюеров |
| Approve / нужны правки / ревью | ✅ / 🛠 / 💬, комментарии к коду из одного ревью одной карточкой, файлы | автора PR |
| Комментарий в PR | 💬 с цитатой | автора PR |
| PR влит | 🟣 с напоминанием перевести задачу в Resolved | автора PR |
| PR закрыт без слияния | ⚫ | никого |

Автора действия бот не отмечает. Отменённые сборки и комментарии ботов не публикуются.
Длинные цитаты сворачиваются.

**Связь GitHub и Telegram**

Каждый участник один раз пишет боту в группе `/link <github-логин>`. Бот проверяет, что такой
пользователь есть на GitHub, и дальше отмечает человека в Telegram. Пока связи нет, вместо отметки
стоит ссылка на профиль GitHub. Один логин можно связать только с одним аккаунтом Telegram.

**Команды**

- `/link <логин>`, `/unlink`, `/people` — связь GitHub и Telegram
- `/changelog` — влитые PR за 14 дней, `/changelog 7d`, `/changelog 29.09`, `/changelog 29.09 12.10`
- `/chatid` — id чата и темы для настройки

Changelog раскладывается по разделам по префиксу заголовка PR (`feat:`, `fix:`, `docs:` …, как в
регламенте). Номер задачи Redmine берётся из ветки `feature/17XXX-...` или из описания PR.

## Как это работает

Бот раз в `POLL_INTERVAL` секунд опрашивает GitHub REST API: PR, ревью, комментарии, запуски
Actions. Вебхуки и права админа в организации не нужны, хватит токена на чтение публичных
репозиториев. Повторные запросы идут с ETag и почти не тратят лимит API.

Что уже обработано, хранится в SQLite. При первом запуске бот запоминает текущее состояние и
ничего не шлёт, уведомления начинаются с новых событий.

```
GitHub ──► github/        клиент REST API, JSON → модели
             │
             ▼
           watcher/       сканер находит новые события, наблюдатель раздаёт их обработчикам
             │
             ▼  domain/events.py: PullRequestOpened, ReviewSubmitted, BuildFinished, …
           обработчики ─► telegram/notifier.py   карточка в тему группы
                       └► (место для синхронизации статусов Redmine)

Команды Telegram ──► telegram/handlers/ ──► people/, changelog/   логика команд без Telegram
```

| Пакет | Что внутри |
|---|---|
| `domain/` | модели, события, соглашения команды (ветка `feature/17XXX-…`, conventional commits) |
| `github/`, `redmine/` | клиенты внешних API; наружу выходят модели и `GitHubError` |
| `watcher/` | состояние в SQLite, сканер репозитория, цикл наблюдения |
| `people/` | связь GitHub-логинов с Telegram |
| `changelog/` | сборка changelog за период |
| `telegram/` | всё про Telegram: разметка, карточки, правила публикации, команды |
| `app.py` | точка сборки зависимостей |

Новый обработчик событий — класс с методом `async handle(event)`, его нужно добавить в список
обработчиков в `app.py`.

## Запуск

1. Создать бота у [@BotFather](https://t.me/BotFather), добавить в группу.
2. Создать [fine-grained token](https://github.com/settings/personal-access-tokens/new)
   с доступом *Public repositories (read-only)*.
3. Заполнить `.env` (шаблон в `.env.example`) и запустить, как показано ниже. `TELEGRAM_CHAT_ID` пока не нужен:
   без него бот отвечает на команды, но уведомления не шлёт.
4. Написать `/chatid` в нужной теме группы, вписать id в `TELEGRAM_CHAT_ID` и `TELEGRAM_THREAD_ID`, перезапустить.

Запуск:

```sh
pip install -e .   # -e: команда changelog-bot идёт по коду из этой папки, правки видны сразу
changelog-bot
```

Или в Docker:

```sh
docker build -t changelog-bot .
docker run -d --env-file .env -v changelog-bot-data:/data --restart unless-stopped changelog-bot
```

## Попробовать в личке

1. В `.env` нужен только `TELEGRAM_BOT_TOKEN`, остальное можно не заполнять.
2. Запустите `changelog-bot --demo` (или `python -m bot --demo`). Это обычный бот со всеми командами,
   но без наблюдения за репозиториями.
3. В личке боту: `/link <ваш-github-логин>`, затем `/demo` — придут примеры всех карточек, автором PR
   в них будете вы. `/changelog 15.09` покажет настоящие PR команды, `/chatid` — id этого чата.
4. Для настоящей работы в личке впишите id из `/chatid` в `TELEGRAM_CHAT_ID`, добавьте `GITHUB_TOKEN`
   и запустите `changelog-bot` без `--demo`.

Чтобы получить события, не трогая репозитории команды, заведите тестовый репозиторий у себя:
`GITHUB_ORG=<ваш логин>`, `GITHUB_REPOS=<репозиторий>`.

## Деплой в Amvera

Пуш в `master` запускает GitHub Actions ([ci.yml](.github/workflows/ci.yml)): ruff, mypy, pytest, и если всё
зелёное — Actions собирает образ, публикует его в `ghcr.io/griagaf/krpobot` и пушит в git-репозиторий Amvera
[amvera.yml](amvera.yml) с тегом этого коммита. Amvera сама ничего не собирает (сборке не хватает ресурсов
младших тарифов), а скачивает образ и перезапускает бота. На PR запускаются только проверки.

Настройка один раз:

1. В Amvera создать проект с окружением Docker. Переменные из `.env.example` задать на вкладке
   «Переменные» (токены — как секреты). `DB_PATH` не нужен: база лежит в постоянном хранилище `/data`.
2. В GitHub → Settings → Secrets and variables → Actions:
   - Variables: `AMVERA_REPO_URL` — адрес git с вкладки «Репозиторий» проекта в Amvera;
   - Secrets: `AMVERA_USERNAME`, `AMVERA_PASSWORD` — логин и пароль учётной записи Amvera.
3. После первого деплоя сделать образ публичным, иначе Amvera его не скачает: профиль GitHub → Packages →
   `krpobot` → Package settings → Change visibility → Public. В образе только код, токены в него не попадают.

Бот с тем же `TELEGRAM_BOT_TOKEN` должен работать в одном экземпляре: перед деплоем остановите локальный.

## Разработка

```sh
pip install -e ".[dev]"
pytest
ruff check . && ruff format --check .
mypy
```
