import asyncio

import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError, TelegramRetryAfter

from bot.domain.events import BuildFinished, CodeCommented, PullRequestCommented, ReviewSubmitted
from bot.telegram.notifier import ChatNotifier, ChatTarget
from bot.telegram.policy import ChatPolicy
from tests import factories as f

REPO = "dejaview-backend"
POLICY = ChatPolicy(notify_build_success=True)


@pytest.mark.parametrize(
    ("event", "allowed"),
    [
        (BuildFinished(REPO, f.run(conclusion="failure")), True),
        (BuildFinished(REPO, f.run()), True),
        (BuildFinished(REPO, f.run(conclusion="cancelled")), False),
        (ReviewSubmitted(REPO, f.pr(), f.review(state="COMMENTED"), ()), False),
        (ReviewSubmitted(REPO, f.pr(), f.review(state="COMMENTED"), (f.review_comment(),)), True),
        (ReviewSubmitted(REPO, f.pr(), f.review(state="DISMISSED"), ()), False),
        (ReviewSubmitted(REPO, f.pr(), f.review(bot=True), ()), False),
        (PullRequestCommented(REPO, f.pr(), f.pr_comment(bot=True)), False),
        (CodeCommented(REPO, f.pr(), (f.review_comment(bot=True),)), False),
    ],
)
def test_policy(event, allowed):
    assert POLICY.allows(event) is allowed


def test_build_success_can_be_muted():
    assert not ChatPolicy(notify_build_success=False).allows(BuildFinished(REPO, f.run()))


class FakeBot:
    def __init__(self, *errors):
        self.errors = list(errors)
        self.sent = []

    async def send_message(self, chat_id, text, message_thread_id=None):
        if self.errors:
            raise self.errors.pop(0)
        self.sent.append((chat_id, message_thread_id, text))


def notify(bot, event=None):
    notifier = ChatNotifier(bot, ChatTarget(-100, 7), f.view(), POLICY)
    asyncio.run(notifier.handle(event or BuildFinished(REPO, f.run(conclusion="failure"))))


def test_sends_card_to_topic():
    bot = FakeBot()
    notify(bot)
    [(chat, thread, text)] = bot.sent
    assert (chat, thread) == (-100, 7) and "Сборка упала" in text


def test_waits_out_flood_limit(monkeypatch):
    async def no_sleep(seconds):
        pass

    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    bot = FakeBot(TelegramRetryAfter(method=None, message="flood", retry_after=3))
    notify(bot)
    assert len(bot.sent) == 1


def test_rejected_message_is_skipped_so_it_cannot_block_the_repo():
    bot = FakeBot(TelegramBadRequest(method=None, message="can't parse entities"))
    notify(bot)
    assert bot.sent == []


def test_network_error_propagates_for_retry():
    with pytest.raises(TelegramNetworkError):
        notify(FakeBot(TelegramNetworkError(method=None, message="timeout")))
