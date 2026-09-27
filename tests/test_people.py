import asyncio
import sqlite3

import pytest

from bot.people import InvalidLoginError, LoginTakenError, PeopleService, PeopleStore, Person, UnknownLoginError
from tests import factories as f
from tests.fakes import FakeGitHub


@pytest.fixture
def store():
    return PeopleStore(sqlite3.connect(":memory:"))


@pytest.fixture
def service(store):
    github = FakeGitHub()
    github.users = {"UsusCimex", "octocat"}
    return PeopleService(store, github)


def link(service, login, tg_id=1, name="Гриша"):
    return asyncio.run(service.link(login, tg_id, name))


def test_link_stores_canonical_login(service, store):
    assert link(service, "@ususcimex").github_login == "UsusCimex"
    assert store.find("USUSCIMEX") == Person("UsusCimex", 1, "Гриша")


@pytest.mark.parametrize(
    ("login", "error"), [("", InvalidLoginError), ("a b", InvalidLoginError), ("ghost", UnknownLoginError)]
)
def test_link_rejects_bad_logins(service, login, error):
    with pytest.raises(error):
        link(service, login)


def test_login_of_someone_else_cannot_be_taken(service):
    link(service, "octocat", tg_id=1, name="Кот")
    with pytest.raises(LoginTakenError) as err:
        link(service, "octocat", tg_id=2)
    assert err.value.owner.tg_name == "Кот"


def test_relinking_replaces_previous_login(service, store):
    link(service, "octocat")
    link(service, "UsusCimex")
    assert [p.github_login for p in store.all()] == ["UsusCimex"]


def test_unlink(service):
    link(service, "octocat")
    assert service.unlink(1) == Person("octocat", 1, "Гриша")
    assert service.unlink(1) is None


def test_view_names_and_mentions():
    view = f.view(("student",))
    assert view.mention("STUDENT") == '<a href="tg://user?id=1">Student</a>'
    assert view.name("student") == "<b>Student</b>"
    assert view.name("ghost") == '<a href="https://github.com/ghost">ghost</a>'


def test_telegram_names_are_escaped(store):
    store.save(Person("x", 1, "<b>хакер</b>"))
    view = f.View(store, str, f.PROJECT)
    assert "&lt;b&gt;" in view.mention("x")


def test_link_keeps_telegram_username(service, store):
    asyncio.run(service.link("octocat", 1, "Кот", "cat_tg"))
    assert store.find("octocat").tg_username == "cat_tg"


def test_store_of_previous_version_gains_username_column():
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE people (github_login TEXT PRIMARY KEY COLLATE NOCASE, tg_id INTEGER, tg_name TEXT)")
    db.execute("INSERT INTO people VALUES ('octocat', 1, 'Кот')")
    assert PeopleStore(db).find("octocat") == Person("octocat", 1, "Кот", None)
