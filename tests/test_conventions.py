import pytest

from bot.domain.conventions import ChangeTitle, task_id
from tests import factories as f


def test_task_from_branch_then_text():
    assert task_id(f.pr(branch="feature/17653-image-search")) == 17653
    assert task_id(f.pr(branch="fix-typo", body="https://ai.nsu.ru/issues/17640\n...")) == 17640
    assert task_id(f.pr(branch="fix-typo", title="fix: #17641 опечатка")) == 17641
    assert task_id(f.pr(branch="fix-typo", body="см. #12")) is None


@pytest.mark.parametrize(
    ("title", "kind", "text"),
    [
        ("feat(search): поиск по кадру", "feat", "search: поиск по кадру"),
        ("FIX!: падение", "fix", "падение"),
        ("ci: сборка", "other", "сборка"),
        ("Поправил всё", "other", "Поправил всё"),
    ],
)
def test_change_title(title, kind, text):
    assert ChangeTitle.parse(title) == ChangeTitle(kind, text)
