from datetime import datetime, timezone

import pytest

from core.projection.facts import PostKey
from core.projection.membership_history import MembershipRow
from core.projection.people import Membership
from core.projection.post_labels import post_role_labels
from shared.schemas import Role, RoleConfig
from shared.utils.taxonomy import build_taxonomy

_TAXONOMY = build_taxonomy(RoleConfig(roles=[Role(id="member", label="Member"), Role(id="mayor", label="Mayor")]))
_COUNCIL = "org-council"
_POST = PostKey(organization_id=_COUNCIL, role_id="member", division_ocdid="ocd-division/country:us/state:zz/place:x")
_EARLY = datetime(2026, 3, 1, tzinfo=timezone.utc)
_LATE = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _row(person_id: str, role_text: str | None, opened_at: datetime, post: PostKey = _POST) -> MembershipRow:
    return MembershipRow(
        person_id=person_id,
        membership=Membership(post=post, opened_at=opened_at, role_text=role_text),
        opened_at=opened_at,
    )


@pytest.mark.unit
def test_a_post_is_named_as_its_newest_members_page_wrote_it():
    history = [_row("ana", "Councilor", _EARLY), _row("ben", "City Councilor", _LATE)]

    assert post_role_labels(history, {}, _TAXONOMY) == {_POST.post_id: "City Councilor"}


@pytest.mark.unit
def test_an_older_wording_names_it_when_the_newest_page_did_not():
    history = [_row("ana", "Councilor", _EARLY), _row("ben", None, _LATE)]

    assert post_role_labels(history, {}, _TAXONOMY) == {_POST.post_id: "Councilor"}


@pytest.mark.unit
def test_with_no_page_wording_the_organizations_label_names_it():
    history = [_row("ana", None, _EARLY)]

    labels = post_role_labels(history, {_COUNCIL: {"member": "Select Board Member"}}, _TAXONOMY)

    assert labels == {_POST.post_id: "Select Board Member"}


@pytest.mark.unit
def test_else_the_roles_own_label_names_it():
    assert post_role_labels([_row("ana", None, _EARLY)], {}, _TAXONOMY) == {_POST.post_id: "Member"}


@pytest.mark.unit
def test_a_post_on_the_unmatched_placeholder_is_called_unmatched():
    post = _POST.model_copy(update={"role_id": "unmatched"})

    assert post_role_labels([_row("ana", None, _EARLY, post)], {}, _TAXONOMY) == {post.post_id: "Unmatched"}
