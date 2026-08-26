import difflib

import pytest

from core.people_edits import (
    PeopleValidationError,
    PersonPatch,
    apply_people_patch,
    patch_people,
    validate_and_normalize,
)
from shared.utils.person_fields import PERSON_FIELD_ORDER
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
        "source_urls": ["https://x.gov/council"],
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


def _fails(entry, fields):
    with pytest.raises(PeopleValidationError) as exc:
        validate_and_normalize([entry], [PersonPatch(id=entry["id"], fields=fields)])
    return exc.value.failures


def test_duplicate_email_names_the_person_and_field():
    entry = _valid("a")
    entry["emails"] = ["mayor@x.gov", "mayor@x.gov"]
    failure = _fails(entry, {"emails": entry["emails"]})[0]
    assert (failure["id"], failure["name"], failure["field"]) == ("a", "Alice", "emails")
    assert "listed twice" in failure["message"]


# Case alone is not a second value — the same rule rowError applies in the editor.
def test_duplicate_ignores_case():
    entry = _valid("a")
    entry["emails"] = ["Mayor@X.gov", "mayor@x.gov"]
    assert _fails(entry, {"emails": entry["emails"]})[0]["field"] == "emails"


# Two spellings of one number canonicalize to the same value, so the check has to run
# after Official has normalized them or it reads them as two numbers.
def test_duplicate_phone_is_caught_after_canonicalization():
    entry = _valid("a", phones=["(916) 808-5300", "916-808-5300"])
    assert _fails(entry, {"phones": entry["phones"]})[0]["field"] == "phones"


# Blank rows are dropped or tolerated by Official, so two of them are not a duplicate.
def test_blank_entries_are_not_duplicates():
    entry = _valid("a")
    entry["other_names"] = ["", "  "]
    assert validate_and_normalize([entry], [PersonPatch(id="a", fields={"other_names": entry["other_names"]})])


# A published record with no source is unverifiable. Enforced here rather than on
# `Official` because the pipelines build that too, and a scrape that found no source
# must still produce a record.
def test_person_with_no_source_url_is_rejected():
    entry = _valid("a")
    entry["source_urls"] = []
    failure = _fails(entry, {"source_urls": []})[0]
    assert (failure["id"], failure["field"]) == ("a", "source_urls")
    assert "source url" in failure["message"]


def test_blank_source_url_does_not_count_as_a_source():
    entry = _valid("a")
    entry["source_urls"] = ["   "]
    assert _fails(entry, {"source_urls": ["   "]})[0]["field"] == "source_urls"


def test_distinct_values_pass():
    entry = _valid("a")
    entry["emails"] = ["mayor@x.gov", "clerk@x.gov"]
    assert validate_and_normalize([entry], [PersonPatch(id="a", fields={"emails": entry["emails"]})])


# The headline guarantee, end-to-end on real YAML: editing one field changes only that line.
# Nulls are explicit `null` (the canonical form the manager emits), so they round-trip
# untouched — only the edited field's line moves.
FIXTURE = """\
- name: Alice Adams
  phones:
  - (916) 808-5300
  emails: []
  office:
    name: Mayor
    division_ocdid: ocd-division/country:us/state:ca/place:x
  cdn_image: null
  updated_at: '2025-11-18T19:49:42+00:00'
  id: a
- name: Bob Brown
  phones: []
  emails:
  - bob@example.org
  office:
    name: Council Member
    division_ocdid: ocd-division/country:us/state:ca/place:x
  cdn_image: null
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


# ── patch_people: every written person lands in Official field order ──────

OFFICIAL_KEYS = list(PERSON_FIELD_ORDER)


def _out_of_order(pid):
    # What the frontend's Add builds: id first, then the rest.
    entry = {
        **_valid(pid),
        "other_names": [],
        "start_date": None,
        "end_date": None,
        "image": None,
        "cdn_image": None,
    }
    return {"id": entry.pop("id"), **entry}


def test_new_person_is_written_in_official_order():
    new = _out_of_order("d")
    people = patch_people([], [PersonPatch(id="d", fields=new)])
    assert list(people[0]) == OFFICIAL_KEYS


def test_untouched_base_person_is_reordered_too():
    base = [_out_of_order("a")]
    people = patch_people(base, [PersonPatch(id="a", fields={})])
    assert list(people[0]) == OFFICIAL_KEYS


def test_reordering_does_not_normalize_untouched_values():
    # Order is the only thing patch_people imposes: the non-canonical phone was not edited,
    # so it must survive verbatim even though its key moved.
    base = [_out_of_order("a")]
    base[0]["phones"] = ["9168085300"]
    people = patch_people(base, [PersonPatch(id="a", fields={"name": "Alice B."})])
    assert people[0]["phones"] == ["9168085300"]
    assert list(people[0]) == OFFICIAL_KEYS


def test_already_ordered_file_only_moves_the_edited_line():
    base = yaml_load(yaml_dump([_valid("a"), _valid("b")]))
    before = yaml_dump(base)
    edits = [
        PersonPatch(id="a", fields={}),
        PersonPatch(id="b", fields={"phones": ["(202) 555-0143"]}),
    ]
    after = yaml_dump(patch_people(base, edits))
    changed = [
        line for line in difflib.unified_diff(before.splitlines(), after.splitlines(), n=0)
        if line[:1] in "+-" and not line.startswith(("+++", "---"))
    ]
    assert changed == ["-  - (916) 808-5300", "+  - (202) 555-0143"]


# --- the edit path against a roster the renderer actually produced ---------------


def _rendered_roster() -> list[dict]:
    """Not a hand-written fixture: the real output of `roster_from_rows`.

    Every existing test here builds its base dict by hand, which is how the roster losing
    `office` went unnoticed while `validate_and_normalize` still required it — the fixtures
    kept a key production had stopped sending, and 780 tests stayed green while every
    reviewer save would have failed with "office: Field required".
    """
    from unittest.mock import MagicMock

    from core.people_roster import roster_from_rows
    from shared.schemas import RoleConfig
    from shared.utils.taxonomy import build_taxonomy

    jurisdiction = "ocd-jurisdiction/country:us/state:tx/place:alpha/government"
    roster, _ = roster_from_rows(
        [
            {
                "name": "Ann Lee",
                "label": "Council Member Place 2",
                "source_url": "https://alpha.gov/council",
                "phone": "(512) 978-2100",
            }
        ],
        {},
        build_taxonomy(RoleConfig(roles=[])),
        jurisdiction,
        MagicMock(),
    )
    return roster


@pytest.mark.unit
def test_a_rendered_roster_survives_the_edit_path():
    base = _rendered_roster()
    assert "office" not in base[0]

    patched = patch_people(base, [PersonPatch(id=base[0]["id"], fields={"emails": ["ann@alpha.gov"]})])

    assert patched[0]["emails"] == ["ann@alpha.gov"]
    assert patched[0]["labels"] == ["Council Member Place 2"]
    assert patched[0]["name"] == "Ann Lee"


@pytest.mark.unit
def test_an_edit_to_a_rendered_roster_still_canonicalises_a_phone():
    """The validators are the only reason the edit path goes through a model at all."""
    base = _rendered_roster()
    patched = patch_people(base, [PersonPatch(id=base[0]["id"], fields={"phones": ["512 978 2100"]})])
    assert patched[0]["phones"] == ["(512) 978-2100"]
