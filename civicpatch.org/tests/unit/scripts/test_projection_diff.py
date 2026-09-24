"""The pure piece of the step 8 dry run: telling a label the taxonomy cannot place from one it
walked past. The diff itself is the script run against a real database, not a mocked one."""

import pytest

from scripts.projection_diff import known_role_in
from shared.schemas import Role, RoleConfig, RoleStatus
from shared.utils.taxonomy import build_taxonomy


def _role(id_, label, aliases):
    return Role(
        id=id_,
        label=label,
        status=RoleStatus.ACTIVE,
        aliases=aliases,
        priority=100,
        is_unique=False,
    )


TAXONOMY = build_taxonomy(
    RoleConfig(
        roles=[
            _role("mayor", "Mayor", []),
            _role("council-member", "Council Member", ["Councilman"]),
            _role("supervisor", "Supervisor", ["Board of Supervisors"]),
        ]
    )
)


@pytest.mark.unit
def test_a_role_named_inside_an_unplaced_label_is_a_bug():
    """What the dry run is asked to count: the taxonomy carries this office, so landing the
    membership in `unmatched` is the parse walking past it, not the taxonomy's scope."""
    assert known_role_in("Board of Supervisors, 2nd District", TAXONOMY) == "Supervisor"


@pytest.mark.unit
def test_an_office_the_taxonomy_does_not_carry_is_not():
    """Sheriff and District Attorney are county offices we do not track on purpose. A label
    naming one belongs in `unmatched`, and reporting it as a bug would bury the real ones."""
    assert known_role_in("Sheriff-Coroner", TAXONOMY) is None


@pytest.mark.unit
def test_an_alias_counts_the_same_as_the_role_s_own_label():
    assert known_role_in("Senior Councilman At Large", TAXONOMY) == "Council Member"


@pytest.mark.unit
def test_a_designation_alone_names_no_role():
    """"Ward 3" is where an office is, not which office it is."""
    assert known_role_in("Ward 3", TAXONOMY) is None


@pytest.mark.unit
def test_the_longest_run_of_words_wins():
    """"Board of Supervisors" is a role in its own right, so answering "Supervisor" from the
    last word alone would name the same role by luck and a different one as soon as they part."""
    assert known_role_in("Clerk to the Board of Supervisors", TAXONOMY) == "Supervisor"
