from bot.domain.models import ReviewRequests
from bot.domain.project import Project, Reviewers

MAINTAINERS = ("ptrvsrg", "UsusCimex", "ykhdr", "skpntsv", "tatyanakrivonogova")
PROJECT = Project(org="dejaview-nsu", teams={"maintainers": MAINTAINERS})
TEAM = ReviewRequests(teams=("maintainers",))
NOBODY = ReviewRequests()


def reviewers(requests, code_owners=NOBODY, author="student"):
    return PROJECT.reviewers(requests, code_owners, author)


def test_team_owning_code_gives_way_to_personal_owner():
    # ml: * @skpntsv @dejaview-nsu/maintainers
    owners = ReviewRequests(("skpntsv",), ("maintainers",))
    assert reviewers(TEAM, owners) == Reviewers(("skpntsv",), ())


def test_whole_team_when_code_has_no_personal_owner():
    # backend: * @dejaview-nsu/maintainers
    assert reviewers(TEAM, ReviewRequests(teams=("maintainers",))).logins == MAINTAINERS


def test_whole_team_but_author_when_author_owns_the_code():
    # docs: * @ykhdr @dejaview-nsu/maintainers, PR открыл сам ykhdr
    owners = ReviewRequests(("ykhdr",), ("maintainers",))
    assert reviewers(TEAM, owners, author="YKHDR").logins == ("ptrvsrg", "UsusCimex", "skpntsv", "tatyanakrivonogova")


def test_team_requested_by_hand_is_not_narrowed():
    # команду позвали вручную, по CODEOWNERS код ей не принадлежит
    owners = ReviewRequests(("skpntsv",), ("ml",))
    assert reviewers(TEAM, owners).logins == MAINTAINERS


def test_requested_people_are_kept_and_not_repeated():
    requests = ReviewRequests(("SKPNTSV", "architect"), ("maintainers",))
    owners = ReviewRequests(("skpntsv",), ("maintainers",))
    assert reviewers(requests, owners).logins == ("SKPNTSV", "architect")


def test_team_without_members_is_reported():
    assert reviewers(ReviewRequests(teams=("qa",))) == Reviewers((), ("qa",))
