FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DB_PATH=/data/bot.sqlite3

WORKDIR /app
COPY pyproject.toml .
COPY bot bot
RUN pip install . \
    && useradd --system --create-home bot \
    && mkdir /data \
    && chown bot /data

USER bot
VOLUME /data
CMD ["changelog-bot"]
