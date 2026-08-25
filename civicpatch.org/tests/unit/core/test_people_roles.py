import pytest

from core.people_roles import derive_roles
from shared.schemas import Role, RoleConfig, RoleStatus
from shared.utils.official_fields import office_name_to_labels
from shared.utils.taxonomy import build_taxonomy

# Pure — taxonomy in, structure out. The insert that stores this lives in
# tests/integration/database/test_source_records.py.

JURISDICTION = "ocd-jurisdiction/country:us/state:tx/place:alpha/government"
BASE = "ocd-division/country:us/state:tx/place:alpha"


def _role(id_, label, aliases, priority):
    return Role(
        id=id_,
        label=label,
        status=RoleStatus.ACTIVE,
        aliases=aliases,
        priority=priority,
        is_unique=False,
    )


TAXONOMY = build_taxonomy(
    RoleConfig(
        roles=[
            _role("mayor", "Mayor", [], 10),
            _role("mayor-pro-tem", "Mayor Pro Tem", ["Mayor Pro-Tem"], 50),
            _role("council-member", "Council Member", ["Councilman"], 500),
            _role("deputy-mayor", "Deputy Mayor", [], 40),
            _role("commissioner", "Commissioner", [], 300),
        ]
    )
)


def _labels(office_name: str) -> list[str]:
    return office_name_to_labels(office_name)


@pytest.mark.unit
def test_parses_role_division_and_seat_out_of_one_label():
    parsed = derive_roles(_labels("Council Member Place 3 (East Ward)"), JURISDICTION, TAXONOMY)
    assert parsed["role"] == "Council Member"
    assert parsed["division_ocdid"] == f"{BASE}/ward:east"
    assert parsed["other_designations"] == ["Place 3"]
    assert parsed["unmatched"] == []


@pytest.mark.unit
def test_the_published_role_is_the_highest_priority_one():
    """Usurp is the lossy step `parsed` exists to record: Mayor Pro Tem (50) over Council
    Member (500), whichever order the label lists them."""
    parsed = derive_roles(_labels("Council Member Place 2 and Mayor Pro-Tem"), JURISDICTION, TAXONOMY)
    assert parsed["role"] == "Mayor Pro Tem"
    assert sorted(parsed["roles"]) == ["Council Member", "Mayor Pro Tem"]


@pytest.mark.unit
def test_an_unknown_office_survives_as_unmatched():
    """The candidate feed: triage reads unresolved labels out of `parsed` rather than a
    separate collection path."""
    parsed = derive_roles(_labels("City Attorney"), JURISDICTION, TAXONOMY)
    assert parsed["role"] is None
    assert parsed["unmatched"] == ["City Attorney"]


@pytest.mark.unit
def test_a_label_naming_no_area_gets_the_jurisdictions_own_division():
    parsed = derive_roles(_labels("Mayor"), JURISDICTION, TAXONOMY)
    assert parsed["division_ocdid"] == BASE


@pytest.mark.unit
def test_a_joined_office_name_splits_back_into_its_labels():
    """Historic records rendered several labels into one string; the split is the first
    lossy step being recorded."""
    parsed = derive_roles(_labels("Council Member Place 2 - Mayor Pro-Tem"), JURISDICTION, TAXONOMY)
    assert parsed["labels"] == ["Council Member Place 2", "Mayor Pro-Tem"]
    assert parsed["role"] == "Mayor Pro Tem"


@pytest.mark.unit
def test_an_unknown_office_name_yields_no_labels():
    parsed = derive_roles(_labels("Unknown Office"), JURISDICTION, TAXONOMY)
    assert parsed["labels"] == []
    assert parsed["role"] is None
    assert parsed["unmatched"] == []


@pytest.mark.unit
def test_parts_keep_each_label_with_the_role_it_produced():
    """The flat keys say what the record decided; `parts` says which label decided it.

    Without this the two questions below are unanswerable: whether a leftover part is
    redundant with the post, and whether stray text is a genuine gap or the residue of a
    label that resolved perfectly well.
    """
    parsed = derive_roles(
        _labels("Commissioner Of Public Safety - Deputy Mayor"), JURISDICTION, TAXONOMY
    )

    assert [(part["label"], part["role"]) for part in parsed["parts"]] == [
        ("Commissioner Of Public Safety", "Commissioner"),
        ("Deputy Mayor", "Deputy Mayor"),
    ]
    # Deputy Mayor (40) usurps Commissioner (300), so the demoted part is the one that
    # carries text the post label will not.
    assert parsed["role"] == "Deputy Mayor"


@pytest.mark.unit
def test_residue_stays_with_the_part_that_produced_it():
    """"Of Public Safety" is not unclassifiable — its label resolved to Commissioner. Flat
    `unmatched` cannot express that; a part carrying both a role and its own residue can."""
    parsed = derive_roles(
        _labels("Commissioner Of Public Safety - City Attorney"), JURISDICTION, TAXONOMY
    )

    by_label = {part["label"]: part for part in parsed["parts"]}
    resolved = by_label["Commissioner Of Public Safety"]
    gap = by_label["City Attorney"]

    assert resolved["role"] == "Commissioner" and resolved["unmatched"] == ["Of Public Safety"]
    assert gap["role"] is None and gap["unmatched"] == ["City Attorney"]
    # Flattened, the two are indistinguishable — which is the bug.
    assert parsed["unmatched"] == ["Of Public Safety", "City Attorney"]


@pytest.mark.unit
def test_there_is_one_part_per_label():
    parsed = derive_roles(_labels("Mayor - Council Member"), JURISDICTION, TAXONOMY)

    assert [part["label"] for part in parsed["parts"]] == parsed["labels"]
