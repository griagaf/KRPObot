import argparse
import asyncio
import logging
import sys

from bot.app import run
from bot.config import ConfigError, Settings


def main() -> None:
    parser = argparse.ArgumentParser(prog="changelog-bot", description="Telegram-бот DejaView")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="без наблюдения за репозиториями: команды и /demo с примерами карточек, нужен только TELEGRAM_BOT_TOKEN",
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
