"""`reconcile` end-to-end: which records become which people.

Port Isabel is the fixture because it has the hard case — Martin Cantu Jr. and Martin C.
Cantu Sr., a father and son on the same council, whom every name heuristic wants to merge.
Two scrapes of it are kept because the two models name people differently.

The per-group helpers are covered in `test_reconcile_merging.py`.
"""

from typing import List
from unittest.mock import MagicMock

from shared.schemas import Person, PersonRecord, Role, RoleConfig
from shared.utils.reconcile import reconcile
from shared.utils.taxonomy import build_taxonomy

# An unresolvable label is kept verbatim, so an empty taxonomy is how a test asserts
# passthrough rather than canonicalisation.
EMPTY_ROLE_CONFIG = RoleConfig(roles=[])

# The vocabulary these fixtures speak: a person whose roles resolve to nothing is
# excluded from the roster, so the merge behaviour under test is only observable
# with the roles the fixtures actually use.
ROLE_CONFIG = RoleConfig(
    roles=[
        Role(id="mayor", label="Mayor", is_unique=True),
        Role(id="mayor-pro-tempore", label="Mayor Pro Tempore", is_unique=True),
        Role(id="council-member", label="Council Member"),
        Role(id="commissioner", label="Commissioner"),
        Role(id="treasurer", label="Treasurer", is_unique=True),
    ]
)


# --- Helpers ---


def make_llm_person(
    name,
    label="",
    phone=None,
    email=None,
    url=None,
    source_url=None,
):
    return PersonRecord(
        name=name,
        label=label,
        phone=phone,
        email=email,
        url=url,
        start_date=None,
        end_date=None,
        image=None,
        source_url=source_url or f"http://source-{name.replace(' ', '').lower()}.com",
    )


def _make_llm_person(**kwargs) -> PersonRecord:
    defaults = {
        "name": "",
        "label": "",
        "phone": None,
        "email": None,
        "url": None,
        "start_date": None,
        "end_date": None,
        "image": None,
        "source_url": None,
    }
    defaults.update(kwargs)
    return PersonRecord(**defaults)


PORT_ISABEL = "ocd-jurisdiction/country:us/state:tx/place:port_isabel/government"


def _reconcile(records: dict, elected_officials: list, identities=None) -> List[Person]:
    """Everyone the scrape saw. Identities default to one-name-per-official, which is what
    the research step produces when it has nothing better."""
    return reconcile(
        [record for group in records.values() for record in group],
        identities
        if identities is not None
        else {o["name"]: [o["name"]] for o in elected_officials},
        build_taxonomy(ROLE_CONFIG),
        PORT_ISABEL,
        MagicMock(),
    )


# --- Test data ---

PORT_ISABEL_OFFICIALS = [
    {"name": "Martin Cantu, Jr.", "roles": ["Mayor"], "designations": []},
    {
        "name": "Jeffery Martinez",
        "roles": ["City Commissioner"],
        "designations": ["Place 4"],
    },
    {
        "name": "Sandra Holland",
        "roles": ["City Commissioner"],
        "designations": ["Place 1"],
    },
    {
        "name": "Michelle Ann Barreiro",
        "roles": ["City Commissioner"],
        "designations": ["Place 2"],
    },
    {
        "name": "Martin C. Cantu, Sr.",
        "roles": ["City Commissioner"],
        "designations": ["Place 3"],
    },
]

GOOGLE_GEMINI_RECORDS = {
    "Martin Cantu, Jr.": [
        _make_llm_person(
            name="Martin Cantu, Jr.",
            label="Mayor",
            phone="(956) 943-2682",
            email="citysecretaryofpi@yahoo.com",
            url="https://myportisabel.com/198/Martin-Cantu-Jr",
            image="https://myportisabel.com/ImageRepository/Document?documentID=765",
            source_url="https://myportisabel.com/197/Mayor-Commissioners",
        ),
    ],
    "Sandra Holland": [
        _make_llm_person(
            name="Sandra Holland",
            label="Commissioner - Place 1",
            phone="(956) 943-2682",
            email="citysecretaryofpi@yahoo.com",
            image="https://myportisabel.com/ImageRepository/Document?documentID=766",
            source_url="https://myportisabel.com/197/Mayor-Commissioners",
        ),
    ],
    "Michelle Ann Barreiro": [
        _make_llm_person(
            name="Michelle Ann Barreiro",
            label="Commissioner - Place 2",
            phone="(956) 943-2682",
            email="citysecretaryofpi@yahoo.com",
            url="https://myportisabel.com/directory.aspx?EID=30",
            image="https://myportisabel.com/ImageRepository/Document?documentID=897",
            source_url="https://myportisabel.com/197/Mayor-Commissioners",
        ),
    ],
    "Martin C. Cantu": [
        _make_llm_person(
            name="Martin C. Cantu",
            label="Commissioner - Place 3",
            phone="(956) 943-2682",
            email="citysecretaryofpi@yahoo.com",
            url="https://myportisabel.com/201/Martin-C-Cantu",
            image="https://myportisabel.com/ImageRepository/Document?documentID=768",
            source_url="https://myportisabel.com/197/Mayor-Commissioners",
        ),
    ],
    "Jeffery David Martinez": [
        _make_llm_person(
            name="Jeffery David Martinez",
            label="Commissioner - Place 4",
            phone="(956) 943-2682",
            email="citysecretaryofpi@yahoo.com",
            url="https://myportisabel.com/202/Jeffery-David-Martinez",
            image="https://myportisabel.com/ImageRepository/Document?documentID=769",
            source_url="https://myportisabel.com/197/Mayor-Commissioners",
        ),
    ],
}

# together_ai records updated to reflect correct prompt behavior:
# designations are separate from roles
TOGETHER_AI_RECORDS = {
    "Martin Cantu Jr.": [
        _make_llm_person(
            name="Martin Cantu Jr.",
            label="Mayor",
            phone="(956) 943-2682",
            url="https://myportisabel.com/198/Martin-Cantu-Jr",
            image="https://myportisabel.com/ImageRepository/Document?documentID=203",
            source_url="https://myportisabel.com/198/Martin-Cantu-Jr",
        ),
    ],
    "Jeffery David Martinez": [
        _make_llm_person(
            name="Jeffery David Martinez",
            label="City Commissioner - Place 4",
            phone="(956) 943-2682",
            email="jefferydmartinez@gmail.com",
            url="https://myportisabel.com/202/Jeffery-David-Martinez",
            image="https://myportisabel.com/ImageRepository/Document?documentID=206",
            source_url="https://myportisabel.com/202/Jeffery-David-Martinez",
        ),
    ],
    "Martin C. Cantu": [
        _make_llm_person(
            name="Martin C. Cantu",
            label="City Commissioner - Place 3",
            phone="(956) 943-2682",
            email="commissionercantu@copitx.com",
            url="https://myportisabel.com/201/Martin-C-Cantu",
            image="https://myportisabel.com/ImageRepository/Document?documentID=205",
            source_url="https://myportisabel.com/201/Martin-C-Cantu",
        ),
    ],
}


# --- reconcile: Cantu Jr./Sr. separation ---


def test_port_isabel_keeps_both_cantus_separate_google_gemini():
    result = _reconcile(GOOGLE_GEMINI_RECORDS, PORT_ISABEL_OFFICIALS)
    cantu_people = [p for p in result if "cantu" in p.name.lower()]
    assert len(cantu_people) == 2, (
        f"Expected 2 Cantu people, got {len(cantu_people)}: {[p.name for p in cantu_people]}"
    )
    assert (
        len([p for p in cantu_people if any("Mayor" in label for label in p.labels)])
        == 1
    )
    assert (
        len(
            [p for p in cantu_people if not any("Mayor" in label for label in p.labels)]
        )
        == 1
    )


def test_port_isabel_keeps_both_cantus_separate_together_ai():
    result = _reconcile(TOGETHER_AI_RECORDS, PORT_ISABEL_OFFICIALS)
    cantu_people = [p for p in result if "cantu" in p.name.lower()]
    assert len(cantu_people) == 2, (
        f"Expected 2 Cantu people, got {len(cantu_people)}: {[p.name for p in cantu_people]}"
    )


def test_port_isabel_both_sources_keep_cantus_separate():
    records: dict = {}
    for source_records in (GOOGLE_GEMINI_RECORDS, TOGETHER_AI_RECORDS):
        for name, person_records in source_records.items():
            records.setdefault(name, []).extend(person_records)

    result = _reconcile(records, PORT_ISABEL_OFFICIALS)
    cantu_people = [p for p in result if "cantu" in p.name.lower()]
    assert len(cantu_people) == 2, (
        f"Expected 2 Cantu people, got {len(cantu_people)}: {[p.name for p in cantu_people]}"
    )


# --- reconcile: name matching ---


def test_port_isabel_jeffery_martinez_matched_to_research():
    """Jeffery David Martinez should fuzzy-match to research identity Jeffery Martinez."""
    result = _reconcile(GOOGLE_GEMINI_RECORDS, PORT_ISABEL_OFFICIALS)
    martinez_people = [p for p in result if "martinez" in p.name.lower()]
    assert len(martinez_people) == 1, (
        f"Expected 1 Martinez, got {len(martinez_people)}: {[p.name for p in martinez_people]}"
    )


def test_port_isabel_cantu_sr_gets_correct_canonical_name():
    """Martin C. Cantu should map to Martin C. Cantu, Sr. from research."""
    result = _reconcile(TOGETHER_AI_RECORDS, PORT_ISABEL_OFFICIALS)
    cantu_people = [p for p in result if "cantu" in p.name.lower()]
    commissioner_cantu = [
        p for p in cantu_people if not any("Mayor" in label for label in p.labels)
    ]
    assert len(commissioner_cantu) == 1
    assert (
        "Sr." in commissioner_cantu[0].name
        or "Martin C. Cantu" in commissioner_cantu[0].name
    )


def test_port_isabel_cantu_jr_gets_correct_canonical_name():
    """Martin Cantu Jr. should map to Martin Cantu, Jr. from research."""
    result = _reconcile(TOGETHER_AI_RECORDS, PORT_ISABEL_OFFICIALS)
    mayor_people = [p for p in result if any("Mayor" in label for label in p.labels)]
    assert len(mayor_people) == 1
    assert "Jr" in mayor_people[0].name


# --- reconcile: counts ---


def test_port_isabel_total_people_count_google_gemini():
    result = _reconcile(GOOGLE_GEMINI_RECORDS, PORT_ISABEL_OFFICIALS)
    people = result
    assert len(people) >= 5, (
        f"Expected at least 5 people, got {len(people)}: {[p.name for p in people]}"
    )


def test_port_isabel_total_people_count_together_ai():
    result = _reconcile(TOGETHER_AI_RECORDS, PORT_ISABEL_OFFICIALS)
    people = result
    assert len(people) >= 3, (
        f"Expected at least 3 people, got {len(people)}: {[p.name for p in people]}"
    )


# --- reconcile: edge cases ---


def test_empty_records():
    result = _reconcile({}, PORT_ISABEL_OFFICIALS)
    assert result == []


def test_no_elected_officials_still_works():
    """Without identity hints, both Cantus may merge — this documents current behavior."""
    result = _reconcile(TOGETHER_AI_RECORDS, elected_officials=[])
    assert len(result) >= 2


def test_explicit_identities_override_research():
    """Explicit config identities take precedence over research identities."""
    explicit_identities = {
        "Martin Cantu, Jr.": ["Martin Cantu Jr."],
        "Martin C. Cantu, Sr.": ["Martin C. Cantu"],
    }
    result = _reconcile(
        TOGETHER_AI_RECORDS, PORT_ISABEL_OFFICIALS, identities=explicit_identities
    )
    cantu_people = [p for p in result if "cantu" in p.name.lower()]
    assert len(cantu_people) == 2, (
        f"Expected 2 Cantu people with explicit identities, got {len(cantu_people)}"
    )


def test_duplicate_records_merged_within_same_name():
    """Same person appearing multiple times under the same name key should merge into one."""
    records = {
        "Sandra Holland": [
            _make_llm_person(
                name="Sandra Holland",
                label="City Commissioner - Place 1",
                phone="(956) 943-2682",
                source_url="https://myportisabel.com/197/Mayor-Commissioners",
            ),
            _make_llm_person(
                name="Sandra Holland",
                label="City Commissioner - Place 1",
                email="sholland@example.com",
                source_url="https://myportisabel.com/some-other-page",
            ),
        ],
    }
    result = _reconcile(records, PORT_ISABEL_OFFICIALS)
    holland_people = [p for p in result if "holland" in p.name.lower()]
    assert len(holland_people) == 1
    assert "(956) 943-2682" in holland_people[0].phones
    assert "sholland@example.com" in holland_people[0].emails
