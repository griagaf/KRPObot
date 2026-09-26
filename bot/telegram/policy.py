from dataclasses import dataclass

from bot.domain.events import BuildFinished, CodeCommented, PullRequestCommented, RepoEvent, ReviewSubmitted
from bot.domain.models import ReviewState

SHOWN_REVIEW_STATES = {ReviewState.APPROVED, ReviewState.CHANGES_REQUESTED, ReviewState.COMMENTED}


@dataclass(frozen=True)
class ChatPolicy:
    """Какие события стоят сообщения в чате. Остальные обработчики видят все события."""

    notify_build_success: bool

    def allows(self, event: RepoEvent) -> bool:
        match event:
            case BuildFinished(run=run):
                # Отменённые сборки обычно перезапущены новым push, о них молчим.
                return run.failed or (run.succeeded and self.notify_build_success)
            case ReviewSubmitted(review=review, comments=comments):
                empty = review.state == ReviewState.COMMENTED and not review.body.strip() and not comments
                return review.state in SHOWN_REVIEW_STATES and not review.author.is_bot and not empty
            case CodeCommented(comments=comments):
                return not comments[0].author.is_bot
            case PullRequestCommented(comment=comment):
                return not comment.author.is_bot
            case _:
                return True
