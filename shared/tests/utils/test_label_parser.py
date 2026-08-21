import pytest
from shared.schemas import Role, RoleConfig, RoleStatus
from shared.utils.label_parser import division_ocdid, parse_label
from shared.utils.taxonomy import build_taxonomy

_JURISDICTION = "ocd-jurisdiction/country:us/state:tx/place:alpha/government"
_BASE = "ocd-division/country:us/state:tx/place:alpha"


def _role(id_, label, aliases, priority):
    return Role(
        id=id_,
        label=label,
        status=RoleStatus.ACTIVE,
        aliases=aliases,
        priority=priority,
        is_unique=False,
    )


_TAXONOMY = build_taxonomy(
    RoleConfig(
        roles=[
            _role("mayor", "Mayor", [], 10),
            _role("council-president", "Council President", ["President"], 100),
            _role(
                "council-member",
                "Council Member",
                ["Councilmember", "Councilman", "Alderman"],
                500,
            ),
        ]
    )
)


@pytest.mark.parametrize(
    "label, role, division, other_designations, unmatched",
    [
        # Plain role, no designation: the division is the jurisdiction's own.
        ("Mayor", "Mayor", _BASE, [], []),
        ("Councilman", "Council Member", _BASE, [], []),
        # Geographic designations become the division, in either word order.
        ("Ward 3", None, f"{_BASE}/ward:3", [], []),
        ("Councilman, District 6", "Council Member", f"{_BASE}/council_district:6", [], []),
        ("Alderman, 3rd Ward", "Council Member", f"{_BASE}/ward:3", [], []),
        ("1st Ward", None, f"{_BASE}/ward:1", [], []),
        ("District IV", None, f"{_BASE}/council_district:4", [], []),
        # A named ward is a real division — the value need not be numeric, and the direction
        # may sit on either side of the key.
        ("Ward East", None, f"{_BASE}/ward:east", [], []),
        ("North Ward", None, f"{_BASE}/ward:north", [], []),
        ("Councilman, South Ward", "Council Member", f"{_BASE}/ward:south", [], []),
        ("Northwest District", None, f"{_BASE}/council_district:northwest", [], []),
        # Non-geographic designations name a seat, not a place.
        ("Council Member - Place 3", "Council Member", _BASE, ["Place 3"], []),
        ("Posn. 2", None, _BASE, ["Position 2"], []),
        ("At-Large A", None, _BASE, ["At-Large A"], []),
        # At-large without a value only restates the base division.
        ("At-Large", None, _BASE, [], []),
        # Several designations in one label are all captured.
        (
            "Council Member - At-Large - Place 6",
            "Council Member",
            _BASE,
            ["Place 6"],
            [],
        ),
        # Unclassifiable text survives instead of being dropped or fabricated into an ocdid.
        (
            "Ward 3 President, Fire Department",
            "Council President",
            f"{_BASE}/ward:3",
            [],
            ["Fire Department"],
        ),
        # Survives rather than being dropped the way `normalize_designations` drops it —
        # trimmed of its brackets, which are decoration around the signal, not the signal.
        ("Ward 3 (North)", None, f"{_BASE}/ward:3", [], ["North"]),
        # A word before the key that is neither a number nor a direction is not a value —
        # otherwise "Member" would be read as the value of "At-Large".
        ("Council Member At-Large", "Council Member", _BASE, [], []),
        ("", None, _BASE, [], []),
    ],
)
def test_parse_label(label, role, division, other_designations, unmatched):
    parsed = parse_label(label, _TAXONOMY)
    assert parsed.role == role
    assert division_ocdid(parsed, _JURISDICTION) == division
    assert parsed.other_designations == other_designations
    assert parsed.unmatched == unmatched


def test_parse_label_takes_the_highest_priority_role_not_the_first():
    """A label naming two offices is an extractor that failed to split them. Whichever it
    lists first, the highest-priority one is the answer — `Council President` (100) over
    `Council Member` (500)."""
    forward = parse_label("Council Member - Place 2 and Council President", _TAXONOMY)
    backward = parse_label("Council President and Council Member - Place 2", _TAXONOMY)
    assert forward.role == backward.role == "Council President"
    assert sorted(forward.roles) == sorted(backward.roles) == [
        "Council Member",
        "Council President",
    ]


def test_parse_label_prefers_a_numbered_division_to_a_named_one():
    """"District 1 (East Ward)" is one area under its official number and its local name.
    The ocdid needs one answer, and taking the last found made it depend on word order."""
    forward = parse_label("Council Member District 1 (East Ward)", _TAXONOMY)
    backward = parse_label("Council Member (East Ward) District 1", _TAXONOMY)
    for parsed in (forward, backward):
        assert division_ocdid(parsed, _JURISDICTION) == f"{_BASE}/council_district:1"
    assert {(d.designation, d.value) for d in forward.divisions} == {
        ("district", "1"),
        ("ward", "east"),
    }


def test_parse_label_keeps_the_local_name_of_a_numbered_division():
    """The nickname is still evidence when matching two records for the same seat."""
    parsed = parse_label("Council Member District 1 (East Ward)", _TAXONOMY)
    assert ("ward", "east") in {(d.designation, d.value) for d in parsed.divisions}


def test_parse_label_falls_back_to_page_order_when_neither_is_numbered():
    parsed = parse_label("Council Member North Ward (East District)", _TAXONOMY)
    assert division_ocdid(parsed, _JURISDICTION) == f"{_BASE}/ward:north"


def test_parse_label_keeps_the_losing_role():
    """Dropping it would lose that she is also the Place 2 member — and whether that
    becomes a second post is not the parser's call."""
    parsed = parse_label("Council Member - Place 2 and Council President", _TAXONOMY)
    assert "Council Member" in parsed.roles
    assert parsed.other_designations == ["Place 2"]


def test_parse_label_names_one_role_once():
    parsed = parse_label("Mayor", _TAXONOMY)
    assert parsed.role == "Mayor"
    assert parsed.roles == ["Mayor"]


def test_parse_label_does_not_split_a_multi_word_title_into_two_roles():
    """`Council President` contains `President`; the longest match at a position must win
    locally before priority is applied, or a title would outrank itself."""
    parsed = parse_label("Council President", _TAXONOMY)
    assert parsed.roles == ["Council President"]


def test_parse_label_prefers_a_cardinal_before_the_key_to_a_stopword_after_it():
    """From real model output: the after-key rule accepts any non-alias word, so `and` read
    as the ward's value and `ward:west` was lost."""
    parsed = parse_label("Place 2 (West Ward) and Mayor Pro-Tem", _TAXONOMY)
    assert division_ocdid(parsed, _JURISDICTION) == f"{_BASE}/ward:west"
    assert parsed.other_designations == ["Place 2"]


def test_parse_label_never_fabricates_a_division_from_trailing_text():
    """`is_division` used to accept any tail, producing ward:3 president, fire department."""
    parsed = parse_label("Ward 3 President, Fire Department", _TAXONOMY)
    ocdid = division_ocdid(parsed, _JURISDICTION)
    assert ocdid == f"{_BASE}/ward:3"
    assert " " not in ocdid.rsplit("/", 1)[-1]


def test_parse_label_keeps_unmatched_in_original_case():
    parsed = parse_label("Ward 3 FIRE Department", _TAXONOMY)
    assert parsed.unmatched == ["FIRE Department"]


@pytest.mark.parametrize(
    "label, unmatched",
    [
        ("Council Member (Central Seattle)", ["Central Seattle"]),
        ("Council Member, Finance Liaison, Place 3", ["Finance Liaison"]),
        ("Council Member [Interim]", ["Interim"]),
    ],
)
def test_parse_label_trims_punctuation_from_the_edges_of_unmatched(label, unmatched):
    """Brackets and commas around surviving text are decoration left by what was removed
    around them. Kept, they split one taxonomy gap into several, each looking proportionally
    less urgent than the real one — "(Central Seattle)" and "Central Seattle" would never
    add up. Interior punctuation stays, since it may be part of the term."""
    assert parse_label(label, _TAXONOMY).unmatched == unmatched


def test_parse_label_keeps_an_unknown_office_as_unmatched():
    """`city` was a bare alias of at-large, so "City Attorney" parsed to a seat called
    "At-Large Attorney" and left nothing behind — destroying the one signal that says this
    label names an office we do not know yet."""
    for label in ("City Attorney", "City Manager", "City Secretary"):
        parsed = parse_label(label, _TAXONOMY)
        assert parsed.role is None
        assert parsed.other_designations == []
        assert parsed.unmatched == [label]


def test_parse_label_still_reads_citywide_as_at_large():
    """Only the bare alias went; the spellings that actually mean at-large stay."""
    for label in ("Councilman Citywide", "Councilman City Wide"):
        parsed = parse_label(label, _TAXONOMY)
        assert parsed.role == "Council Member"
        assert parsed.unmatched == []


@pytest.mark.parametrize(
    "label", ["District Attorney", "Precinct Chair", "Post Office Liaison", "Ward Downtown"]
)
def test_parse_label_leaves_a_keyword_without_a_valid_value_as_unmatched(label):
    """A designation needs a value to be one. Taking any following word instead read
    "District Attorney" as `district:attorney` and published that as an OCD division id."""
    parsed = parse_label(label, _TAXONOMY)
    assert parsed.divisions == []
    assert parsed.other_designations == []
    assert parsed.unmatched == [label]


@pytest.mark.parametrize(
    "label, expected_ocdid",
    [
        ("Council Member Ward 3", f"{_BASE}/ward:3"),
        ("Council Member Ward 03", f"{_BASE}/ward:3"),
        ("Council Member Ward 003", f"{_BASE}/ward:3"),
    ],
)
def test_parse_label_drops_leading_zeros_from_a_division_value(label, expected_ocdid):
    """Two spellings of one number would mint two ocdids nothing can reconcile after
    the fact — the value has to be normalised before it reaches the identifier."""
    parsed = parse_label(label, _TAXONOMY)
    assert division_ocdid(parsed, _JURISDICTION) == expected_ocdid


def test_parse_label_drops_leading_zeros_from_a_designation_value():
    parsed = parse_label("Council Member Position 07", _TAXONOMY)
    assert parsed.other_designations == ["Position 7"]


def test_parse_label_keeps_a_lone_zero():
    """`lstrip("0")` on "0" leaves nothing; a division value must never be empty."""
    parsed = parse_label("Council Member Ward 0", _TAXONOMY)
    assert division_ocdid(parsed, _JURISDICTION) == f"{_BASE}/ward:0"


@pytest.mark.parametrize(
    "label",
    [
        "Council Member At-Large",
        "Council Member At Large",
        "Council Member Citywide",
        "Council Member City-Wide",
    ],
)
def test_parse_label_swallows_at_large_when_it_carries_no_value(label):
    """The one keyword that means something alone — everything else needs a value.

    It is consumed and recorded nowhere: valueless at-large only restates that the post
    covers the whole jurisdiction, which the division already carries. Recording it
    would put "At-Large" in the post label and split one seat into two posts. Consumed
    rather than ignored, so the tokens cannot fall through to `unmatched` either.
    """
    parsed = parse_label(label, _TAXONOMY)
    assert parsed.role == "Council Member"
    assert parsed.other_designations == []
    assert parsed.unmatched == []
    assert parsed.division is None


@pytest.mark.parametrize(
    "label, designation",
    [
        ("Council Member At-Large A", "At-Large A"),
        ("Council Member At-Large 2", "At-Large 2"),
    ],
)
def test_parse_label_keeps_at_large_when_it_carries_a_value(label, designation):
    """With a value it is the only thing telling two otherwise identical posts apart,
    so it survives as a designation and the division stays the jurisdiction's own."""
    parsed = parse_label(label, _TAXONOMY)
    assert parsed.other_designations == [designation]
    assert parsed.division is None
    assert parsed.unmatched == []


def test_parse_label_keeps_unrelated_fragments_apart():
    """Joining them would produce one nonsense term instead of two real ones."""
    parsed = parse_label("Fire Chief Ward 3 Deputy Marshal", _TAXONOMY)
    assert parsed.unmatched == ["Fire Chief", "Deputy Marshal"]
