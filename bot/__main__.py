import asyncio
import logging
import sys

from bot.app import run
from bot.config import ConfigError, Settings


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        settings = Settings.from_env()
    except ConfigError as err:
        sys.exit(str(err))
    asyncio.run(run(settings))


if __name__ == "__main__":
    main()
