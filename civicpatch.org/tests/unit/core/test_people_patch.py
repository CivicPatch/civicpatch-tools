import difflib

import pytest

from core.people_patch import (
    PeopleValidationError,
    PersonPatch,
    apply_people_patch,
    validate_and_normalize,
)
from shared.utils.yaml_utils import yaml_dump, yaml_load

pytestmark = pytest.mark.unit


def _person(pid, name, phones=None):
    return {"name": name, "phones": phones or [], "office": {"name": "Mayor"}, "id": pid}


BASE = [
    _person("a", "Alice", ["(916) 808-5300"]),
    _person("b", "Bob"),
    _person("c", "Carol"),
]


def test_edit_one_field_leaves_everything_else_untouched():
    result = apply_people_patch(BASE, [
        PersonPatch(id="a", fields={}),
        PersonPatch(id="b", fields={"phones": ["(202) 555-0143"]}),
        PersonPatch(id="c", fields={}),
    ])
    assert result[0] == BASE[0]              # Alice untouched
    assert result[2] == BASE[2]              # Carol untouched
    assert result[1]["phones"] == ["(202) 555-0143"]
    assert {k: result[1][k] for k in result[1] if k != "phones"} == \
           {k: BASE[1][k] for k in BASE[1] if k != "phones"}


def test_edit_preserves_key_order():
    result = apply_people_patch(BASE, [
        PersonPatch(id="a", fields={}),
        PersonPatch(id="b", fields={"phones": ["(202) 555-0143"]}),
        PersonPatch(id="c", fields={}),
    ])
    assert list(result[1].keys()) == list(BASE[1].keys())


def test_unknown_id_is_inserted_whole_as_new_person():
    # The frontend gave this person a backend id at "Add"; that id isn't in the base file,
    # so it's new and `fields` is the whole entry (id included).
    new = {"id": "d", "name": "Dave", "phones": []}
    result = apply_people_patch(BASE, [
        PersonPatch(id="a", fields={}),
        PersonPatch(id="d", fields=new),
        PersonPatch(id="b", fields={}),
        PersonPatch(id="c", fields={}),
    ])
    assert result[1] == new
    assert [p["id"] for p in result] == ["a", "d", "b", "c"]


def test_delete_via_omission():
    result = apply_people_patch(BASE, [
        PersonPatch(id="a", fields={}),
        PersonPatch(id="c", fields={}),
    ])
    assert [p["id"] for p in result] == ["a", "c"]


def test_reorder_only_keeps_entries_identical():
    result = apply_people_patch(BASE, [
        PersonPatch(id="c", fields={}),
        PersonPatch(id="a", fields={}),
        PersonPatch(id="b", fields={}),
    ])
    assert result == [BASE[2], BASE[0], BASE[1]]


def test_no_op_is_identical_to_base():
    result = apply_people_patch(BASE, [PersonPatch(id=p["id"], fields={}) for p in BASE])
    assert result == BASE


def test_unknown_base_field_is_preserved():
    base = [{"name": "Eve", "id": "e", "legacy_note": "keep me"}]
    result = apply_people_patch(base, [PersonPatch(id="e", fields={"name": "Eve B."})])
    assert result[0]["legacy_note"] == "keep me"
    assert result[0]["name"] == "Eve B."


def test_re_id_changes_id_and_keeps_position():
    result = apply_people_patch(BASE, [
        PersonPatch(id="a", fields={}),
        PersonPatch(id="b", fields={"id": "b-canonical"}),
        PersonPatch(id="c", fields={}),
    ])
    assert [p["id"] for p in result] == ["a", "b-canonical", "c"]
    assert list(result[1].keys()) == list(BASE[1].keys())  # id stays in its slot


def test_patched_aligns_one_to_one_with_edits():
    # The id-keyed error scheme rests on this: one output per edit, in edits order.
    edits = [PersonPatch(id="c", fields={}), PersonPatch(id="a", fields={})]
    result = apply_people_patch(BASE, edits)
    assert len(result) == len(edits)
    assert [p["id"] for p in result] == [e.id for e in edits]


# ── validate_and_normalize ────────────────────────────────────────────────

def _valid(pid, name="Alice", phones=None):
    return {
        "name": name,
        "phones": ["(916) 808-5300"] if phones is None else phones,
        "emails": [],
        "urls": [],
        "office": {"name": "Mayor", "division_ocdid": None},
        "jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:ca/place:x/government",
        "source_urls": [],
        "updated_at": "2025-11-18T19:49:42+00:00",
        "id": pid,
    }


def test_validate_normalizes_an_edited_phone():
    entry = _valid("a", phones=["9168085300"])
    people = validate_and_normalize([entry], [PersonPatch(id="a", fields={"phones": ["9168085300"]})])
    assert people[0]["phones"] == ["(916) 808-5300"]


def test_validate_leaves_untouched_fields_unnormalized():
    # The phone is valid-but-non-canonical and was NOT edited (only the name was), so it must
    # stay exactly as the base file has it — normalization applies only to edited fields.
    entry = {**_valid("a", phones=["9168085300"]), "name": "Alice B."}
    people = validate_and_normalize([entry], [PersonPatch(id="a", fields={"name": "Alice B."})])
    assert people[0]["phones"] == ["9168085300"]
    assert people[0]["name"] == "Alice B."


def test_validate_normalizes_all_fields_of_a_new_person():
    new = _valid("d", phones=["9168085300"])
    people = validate_and_normalize([new], [PersonPatch(id="d", fields=new)])
    assert people[0]["phones"] == ["(916) 808-5300"]


def test_validate_raises_failures_keyed_by_id():
    entry = _valid("a", phones=["not-a-phone"])
    with pytest.raises(PeopleValidationError) as exc:
        validate_and_normalize([entry], [PersonPatch(id="a", fields={"phones": ["not-a-phone"]})])
    assert exc.value.failures[0]["id"] == "a"
    assert exc.value.failures[0]["name"] == "Alice"
    assert exc.value.failures[0]["field"] == "phones"


# The headline guarantee, end-to-end on real YAML: editing one field changes only that line.
# Fixture is in post-reformat canonical (ruamel-native) form — blank nulls — which is what
# files look like after the Step 5 bulk reformat. The guarantee holds against that baseline;
# against a PyYAML-spelled (`: null`) base the first edit would also flip nulls to blank,
# which is precisely why the reformat is a prerequisite.
FIXTURE = """\
- name: Alice Adams
  phones:
  - (916) 808-5300
  emails: []
  office:
    name: Mayor
    division_ocdid: ocd-division/country:us/state:ca/place:x
  cdn_image:
  updated_at: '2025-11-18T19:49:42+00:00'
  id: a
- name: Bob Brown
  phones: []
  emails:
  - bob@example.org
  office:
    name: Council Member
    division_ocdid: ocd-division/country:us/state:ca/place:x
  cdn_image:
  updated_at: '2025-11-18T19:49:42+00:00'
  id: b
"""


def test_only_edited_field_moves_end_to_end():
    base = yaml_load(FIXTURE)
    edits = [
        PersonPatch(id="a", fields={}),
        PersonPatch(id="b", fields={"phones": ["(202) 555-0143"]}),
    ]
    new_text = yaml_dump(apply_people_patch(base, edits))
    changed = [
        line for line in difflib.unified_diff(FIXTURE.splitlines(), new_text.splitlines(), n=0)
        if line[:1] in "+-" and not line.startswith(("+++", "---"))
    ]
    assert changed == ["-  phones: []", "+  phones:", "+  - (202) 555-0143"]
