import pytest

from bot.domain.codeowners import CodeOwners, compile_pattern
from bot.domain.models import ReviewRequests


@pytest.mark.parametrize(
    ("pattern", "path", "matches"),
    [
        # примеры из документации GitHub «About code owners»
        ("*", "README.md", True),
        ("*", "src/deep/main.py", True),
        ("*.js", "src/deep/app.js", True),
        ("*.js", "app.jsx", False),
        ("/build/logs/", "build/logs/sub/a.log", True),
        ("/build/logs/", "x/build/logs/a.log", False),
        ("docs/*", "docs/getting-started.md", True),
        ("docs/*", "docs/build-app/troubleshooting.md", False),  # тут GitHub расходится с git
        ("docs/*", "x/docs/a.md", False),
        ("apps/", "x/apps/y/z.txt", True),
        ("apps/", "apps.txt", False),
        ("/docs/", "docs/x/y.md", True),
        ("/docs/", "x/docs/y.md", False),
        ("**/logs", "deeply/nested/logs/a.log", True),
        ("**/logs", "logs/a.log", True),
        ("/apps/github", "apps/github/x.py", True),
        ("/apps/github", "apps/github", True),
        ("/apps/github", "apps/githubx", False),
        ("src/**/test_*.py", "src/a/b/test_x.py", True),
        ("src/**/test_*.py", "src/test_x.py", True),
        ("docs/**", "docs/a/b.md", True),
        ("?.md", "a.md", True),
        ("?.md", "ab.md", False),
        ("\\#notes", "#notes", True),
    ],
)
def test_pattern(pattern, path, matches):
    assert bool(compile_pattern(pattern).fullmatch(path)) is matches


CODEOWNERS = """
# Ревьюер по умолчанию - ментор направления ML.
*       @skpntsv @dejaview-nsu/maintainers
*.md    @writer   # встроенный комментарий
*.txt   docs@example.com @Dejaview-NSU/Docs
/apps/  @octocat
/apps/github
!keep   @nobody
[ab].py @nobody
"""


@pytest.fixture
def owners():
    return CodeOwners.parse(CODEOWNERS)


def test_last_matching_rule_wins(owners):
    assert owners.owners(["model.py"]) == ReviewRequests(("skpntsv",), ("maintainers",))
    assert owners.owners(["README.md"]) == ReviewRequests(("writer",))


def test_emails_are_skipped_and_teams_become_slugs(owners):
    assert owners.owners(["notes.txt"]) == ReviewRequests((), ("docs",))


def test_rule_without_owners_takes_ownership_away(owners):
    assert owners.owners(["apps/github/x.py"]) == ReviewRequests()
    assert owners.owners(["apps/web/x.py"]) == ReviewRequests(("octocat",))


def test_owners_of_several_files_are_merged(owners):
    assert owners.owners(["README.md", "model.py", "apps/web/x.py"]) == ReviewRequests(
        ("writer", "skpntsv", "octocat"), ("maintainers",)
    )


def test_unsupported_rules_are_skipped(owners):
    assert owners.owners(["keep", "a.py"]) == ReviewRequests(("skpntsv",), ("maintainers",))
    assert CodeOwners.parse("").owners(["x"]) == ReviewRequests()
