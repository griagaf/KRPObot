import argparse
import asyncio
import logging
import sys

from bot.app import run
from bot.config import ConfigError, Settings


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="changelog-bot", description="Telegram-бот: уведомления о PR и сборках GitHub, changelog"
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="без наблюдения за репозиториями: команды и /demo с примерами карточек, "
        "нужны только TELEGRAM_BOT_TOKEN и GITHUB_ORG",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        settings = Settings.from_env(watching=not args.demo)
        asyncio.run(run(settings, demo_mode=args.demo))
    except ConfigError as err:
        sys.exit(str(err))


if __name__ == "__main__":
    main()
