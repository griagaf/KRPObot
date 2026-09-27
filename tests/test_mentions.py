import pytest

from bot.domain.mentions import Mentions, mentions


@pytest.mark.parametrize(
    ("text", "users"),
    [
        ("@skpntsv посмотри, пожалуйста", ("skpntsv",)),
        ("Поправил, @ykhdr, @UsusCimex.", ("ykhdr", "UsusCimex")),
        ("(@ptrvsrg) и @ptrvsrg ещё раз, и @PTRVSRG", ("ptrvsrg",)),
        ("пиши на mentor@example.com", ()),
        ("аннотация `@Override` не нужна", ()),
        ("```java\n@Override\nvoid run() {}\n```\nа это @alice", ("alice",)),
        ("> @bob писал, что всё сломано\n@carol глянь", ("carol",)),
        ("@-bad @bad- @ok-login @", ("ok-login",)),
        ("@" + "a" * 40, ()),
    ],
)
def test_user_mentions(text, users):
    assert mentions(text).users == users


def test_team_mentions_become_slugs():
    assert mentions("@dejaview-nsu/Maintainers, глянете?") == Mentions((), ("maintainers",))


def test_several_texts_are_merged():
    assert mentions("@alice", "@bob и @Alice") == Mentions(("alice", "bob"))
