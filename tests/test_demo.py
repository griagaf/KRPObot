from bot.demo import sample_events
from bot.domain.models import User
from bot.telegram import cards
from bot.telegram.policy import ChatPolicy
from tests import factories as f


def test_every_demo_card_passes_policy_and_renders():
    events = sample_events(User("student"))
    view = f.view(("student",))
    assert all(ChatPolicy(notify_build_success=True).allows(e) for e in events)
    for event in events:
        text = cards.render(event, view)
        assert text.split("\n")[0].endswith("· #backend")
        assert len(text) < 4096
