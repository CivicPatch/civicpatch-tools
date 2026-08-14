from unittest.mock import MagicMock

import pytest
from runners.people_collector.schemas import (
    LinkFrontier,
    LLMPersonRecord,
    PeopleCollectorContext,
    PeopleCollectorData,
    Person,
    PipelineRunConfig,
    PreprocessPageContentStep,
    ProcessPageContentStep,
    ResearchMunicipalityStep,
)
from runners.people_collector.steps.step_05_merge_records_within_llm.merge_records_within_llm import (
    get_source_urls,
    merge_llm_people_to_person,
    merge_records_within_llm,
    merge_weak_tie_groups_within_llm,
)
from shared.schemas import RoleConfig, Role
from utils.taxonomy import build_taxonomy

pytestmark = pytest.mark.unit

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
    roles=None,
    designations=None,
    phone=None,
    email=None,
    url=None,
    source_url=None,
):
    return LLMPersonRecord(
        name=name,
        roles=roles or [],
        designations=designations or [],
        phone=phone,
        email=email,
        url=url,
        start_date=None,
        end_date=None,
        image=None,
        source_url=source_url or f"http://source-{name.replace(' ', '').lower()}.com",
    )


def _make_llm_person(**kwargs) -> LLMPersonRecord:
    defaults = {
        "name": "",
        "roles": [],
        "designations": [],
        "phone": None,
        "email": None,
        "url": None,
        "start_date": None,
        "end_date": None,
        "image": None,
        "source_url": None,
    }
    defaults.update(kwargs)
    return LLMPersonRecord(**defaults)


def _build_context(
    records: dict, elected_officials: list, identities=None
) -> PeopleCollectorContext:
    resolved_identities = (
        identities
        if identities is not None
        else {o["name"]: [o["name"]] for o in elected_officials}
    )
    research_step = ResearchMunicipalityStep(
        expected_count=len(elected_officials),
        identities=resolved_identities,
    )
    process_step = ProcessPageContentStep(
        records=records,
        progress={
            "required_data": 5,
            "current_data": 5,
            "has_target_role": True,
            "has_target_designations": True,
        },
    )
    data = PeopleCollectorData(
        jurisdiction_ocdid="ocd-jurisdiction/country:us/state:tx/place:port_isabel/government",
        config=PipelineRunConfig(
            url="https://myportisabel.com/", name="Port Isabel city"
        ),
        role_config=ROLE_CONFIG,
        frontier=LinkFrontier(),
        research_municipality_step=research_step,
        preprocess_page_content_step=PreprocessPageContentStep(
            elapsed_times=[],
            total_elapsed_time_seconds=0,
            average_elapsed_time_seconds=0,
        ),
        process_page_content_step=process_step,
    )
    return PeopleCollectorContext(
        data=data,
        current_state="MERGE_RECORDS_WITHIN_LLM",
        request_id="test-request",
        created_at=0,
        updated_at=0,
        progress=0,
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
            roles=["Mayor"],
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
            roles=["Commissioner"],
            designations=["Place 1"],
            phone="(956) 943-2682",
            email="citysecretaryofpi@yahoo.com",
            image="https://myportisabel.com/ImageRepository/Document?documentID=766",
            source_url="https://myportisabel.com/197/Mayor-Commissioners",
        ),
    ],
    "Michelle Ann Barreiro": [
        _make_llm_person(
            name="Michelle Ann Barreiro",
            roles=["Commissioner"],
            designations=["Place 2"],
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
            roles=["Commissioner"],
            designations=["Place 3"],
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
            roles=["Commissioner"],
            designations=["Place 4"],
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
            roles=["Mayor"],
            phone="(956) 943-2682",
            url="https://myportisabel.com/198/Martin-Cantu-Jr",
            image="https://myportisabel.com/ImageRepository/Document?documentID=203",
            source_url="https://myportisabel.com/198/Martin-Cantu-Jr",
        ),
    ],
    "Jeffery David Martinez": [
        _make_llm_person(
            name="Jeffery David Martinez",
            roles=["City Commissioner"],
            designations=["Place 4"],
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
            roles=["City Commissioner"],
            designations=["Place 3"],
            phone="(956) 943-2682",
            email="commissionercantu@copitx.com",
            url="https://myportisabel.com/201/Martin-C-Cantu",
            image="https://myportisabel.com/ImageRepository/Document?documentID=205",
            source_url="https://myportisabel.com/201/Martin-C-Cantu",
        ),
    ],
}


# --- merge_llm_people_to_person ---


def test_merge_llm_people_to_person():
    p1 = make_llm_person(
        name="Eve",
        roles=["Council Member", "Treasurer"],
        designations=["Ward 5", "Ward 6"],
        phone="(956) 943-2682",
        email="eve@city.org",
        source_url="http://source1.com",
    )
    p2 = make_llm_person(
        name="Eve",
        roles=["Council Member", "Mayor"],
        designations=["Ward 5", "Ward 7"],
        phone="(956) 943-2682",
        email="eve@city.org",
        source_url="http://source2.com",
    )
    result = merge_llm_people_to_person(
        MagicMock(), build_taxonomy(EMPTY_ROLE_CONFIG), "Eve", [p1, p2], "jurisdiction_id"
    )

    assert result.name == "Eve"
    assert set(result.roles) == {"Council Member", "Treasurer", "Mayor"}
    assert set(result.designations) == {"Ward 5", "Ward 6", "Ward 7"}
    assert set(result.phones) == {"(956) 943-2682"}
    assert set(result.emails) == {"eve@city.org"}
    assert set(result.source_urls) == {"http://source1.com", "http://source2.com"}
    assert result.jurisdiction_ocdid == "jurisdiction_id"


# --- get_source_urls ---


def test_get_source_urls_filters_by_unique_contribution():
    r1 = LLMPersonRecord(
        name="Robert Kubert",
        roles=["Mayor"],
        designations=["Ward 1"],
        phone=None,
        email=None,
        url="https://www.bayonnenj.org/officials/bio/mayor-robert-kubert",
        start_date=None,
        end_date=None,
        image=None,
        source_url="https://www.bayonnenj.org/r1",
    )
    r2 = LLMPersonRecord(
        name="Robert Kubert",
        roles=["Mayor", "Council Member"],
        designations=["Ward 2", "Ward 3"],
        phone="555-0002",
        email="mayor2@bayonne.org",
        url="https://www.bayonnenj.org/officials/bio/mayor-robert-kubert",
        start_date=None,
        end_date=None,
        image=None,
        source_url="https://www.bayonnenj.org/r2",
    )
    r3 = LLMPersonRecord(
        name="Robert Kubert",
        roles=["Mayor"],
        designations=["Ward 1"],
        phone=None,
        email=None,
        url="https://www.bayonnenj.org/officials/bio/mayor-robert-kubert",
        start_date=None,
        end_date=None,
        image=None,
        source_url="https://www.bayonnenj.org/r3",
    )

    person = Person(
        name="Robert Kubert",
        roles=["Mayor", "Council Member"],
        designations=["Ward 1", "Ward 2", "Ward 3"],
        phones=["555-0002"],
        emails=["mayor2@bayonne.org"],
        urls=["https://www.bayonnenj.org/officials/bio/mayor-robert-kubert"],
        jurisdiction_ocdid="test_ocdid",
        source_urls=[],
        updated_at="",
    )

    result = get_source_urls([r1, r2, r3], person)
    assert set(result) == {
        "https://www.bayonnenj.org/r1",
        "https://www.bayonnenj.org/r2",
    }


# --- merge_records_within_llm: Cantu Jr./Sr. separation ---


def test_port_isabel_keeps_both_cantus_separate_google_gemini():
    result = merge_records_within_llm(
        _build_context(GOOGLE_GEMINI_RECORDS, PORT_ISABEL_OFFICIALS)
    )
    cantu_people = [
        p for p in result.records if "cantu" in p.name.lower()
    ]
    assert len(cantu_people) == 2, (
        f"Expected 2 Cantu people, got {len(cantu_people)}: {[p.name for p in cantu_people]}"
    )
    assert len([p for p in cantu_people if "Mayor" in p.roles]) == 1
    assert len([p for p in cantu_people if "Mayor" not in p.roles]) == 1


def test_port_isabel_keeps_both_cantus_separate_together_ai():
    result = merge_records_within_llm(
        _build_context(TOGETHER_AI_RECORDS, PORT_ISABEL_OFFICIALS)
    )
    cantu_people = [
        p for p in result.records if "cantu" in p.name.lower()
    ]
    assert len(cantu_people) == 2, (
        f"Expected 2 Cantu people, got {len(cantu_people)}: {[p.name for p in cantu_people]}"
    )


def test_port_isabel_both_sources_keep_cantus_separate():
    records: dict = {}
    for source_records in (GOOGLE_GEMINI_RECORDS, TOGETHER_AI_RECORDS):
        for name, person_records in source_records.items():
            records.setdefault(name, []).extend(person_records)

    result = merge_records_within_llm(_build_context(records, PORT_ISABEL_OFFICIALS))
    cantu_people = [p for p in result.records if "cantu" in p.name.lower()]
    assert len(cantu_people) == 2, (
        f"Expected 2 Cantu people, got {len(cantu_people)}: {[p.name for p in cantu_people]}"
    )


# --- merge_records_within_llm: name matching ---


def test_port_isabel_jeffery_martinez_matched_to_research():
    """Jeffery David Martinez should fuzzy-match to research identity Jeffery Martinez."""
    result = merge_records_within_llm(
        _build_context(GOOGLE_GEMINI_RECORDS, PORT_ISABEL_OFFICIALS)
    )
    martinez_people = [
        p for p in result.records if "martinez" in p.name.lower()
    ]
    assert len(martinez_people) == 1, (
        f"Expected 1 Martinez, got {len(martinez_people)}: {[p.name for p in martinez_people]}"
    )


def test_port_isabel_cantu_sr_gets_correct_canonical_name():
    """Martin C. Cantu should map to Martin C. Cantu, Sr. from research."""
    result = merge_records_within_llm(
        _build_context(TOGETHER_AI_RECORDS, PORT_ISABEL_OFFICIALS)
    )
    cantu_people = [
        p for p in result.records if "cantu" in p.name.lower()
    ]
    commissioner_cantu = [p for p in cantu_people if "Mayor" not in p.roles]
    assert len(commissioner_cantu) == 1
    assert (
        "Sr." in commissioner_cantu[0].name
        or "Martin C. Cantu" in commissioner_cantu[0].name
    )


def test_port_isabel_cantu_jr_gets_correct_canonical_name():
    """Martin Cantu Jr. should map to Martin Cantu, Jr. from research."""
    result = merge_records_within_llm(
        _build_context(TOGETHER_AI_RECORDS, PORT_ISABEL_OFFICIALS)
    )
    mayor_people = [
        p for p in result.records if "Mayor" in p.roles
    ]
    assert len(mayor_people) == 1
    assert "Jr" in mayor_people[0].name


# --- merge_records_within_llm: counts ---


def test_port_isabel_total_people_count_google_gemini():
    result = merge_records_within_llm(
        _build_context(GOOGLE_GEMINI_RECORDS, PORT_ISABEL_OFFICIALS)
    )
    people = result.records
    assert len(people) >= 5, (
        f"Expected at least 5 people, got {len(people)}: {[p.name for p in people]}"
    )


def test_port_isabel_total_people_count_together_ai():
    result = merge_records_within_llm(
        _build_context(TOGETHER_AI_RECORDS, PORT_ISABEL_OFFICIALS)
    )
    people = result.records
    assert len(people) >= 3, (
        f"Expected at least 3 people, got {len(people)}: {[p.name for p in people]}"
    )


# --- merge_records_within_llm: edge cases ---


def test_empty_records():
    result = merge_records_within_llm(
        _build_context({}, PORT_ISABEL_OFFICIALS)
    )
    assert result.records == []


def test_no_elected_officials_still_works():
    """Without identity hints, both Cantus may merge — this documents current behavior."""
    result = merge_records_within_llm(
        _build_context(TOGETHER_AI_RECORDS, elected_officials=[])
    )
    assert len(result.records) >= 2


def test_explicit_identities_override_research():
    """Explicit config identities take precedence over research identities."""
    explicit_identities = {
        "Martin Cantu, Jr.": ["Martin Cantu Jr."],
        "Martin C. Cantu, Sr.": ["Martin C. Cantu"],
    }
    result = merge_records_within_llm(
        _build_context(
            TOGETHER_AI_RECORDS,
            PORT_ISABEL_OFFICIALS,
            identities=explicit_identities,
        )
    )
    cantu_people = [
        p for p in result.records if "cantu" in p.name.lower()
    ]
    assert len(cantu_people) == 2, (
        f"Expected 2 Cantu people with explicit identities, got {len(cantu_people)}"
    )


def test_duplicate_records_merged_within_same_name():
    """Same person appearing multiple times under the same name key should merge into one."""
    records = {
        "Sandra Holland": [
            _make_llm_person(
                name="Sandra Holland",
                roles=["City Commissioner"],
                designations=["Place 1"],
                phone="(956) 943-2682",
                source_url="https://myportisabel.com/197/Mayor-Commissioners",
            ),
            _make_llm_person(
                name="Sandra Holland",
                roles=["City Commissioner"],
                designations=["Place 1"],
                email="sholland@example.com",
                source_url="https://myportisabel.com/some-other-page",
            ),
        ],
    }
    result = merge_records_within_llm(_build_context(records, PORT_ISABEL_OFFICIALS))
    holland_people = [p for p in result.records if "holland" in p.name.lower()]
    assert len(holland_people) == 1
    assert "(956) 943-2682" in holland_people[0].phones
    assert "sholland@example.com" in holland_people[0].emails


# --- merge_weak_tie_groups_within_llm ---


class TestMergeWeakTieGroupsWithinLlm:
    def test_merges_by_last_name_and_role(self):
        """Last-name-only canonical merges into full-name canonical with same role."""
        groups = {
            "Lindamood": [make_llm_person("Lindamood", roles=["mayor"])],
            "Bobby Lindamood": [
                make_llm_person("Bobby Lindamood", roles=["mayor"], email="b@city.gov")
            ],
        }
        result = merge_weak_tie_groups_within_llm(groups)
        assert "Lindamood" not in result
        assert "Bobby Lindamood" in result
        assert len(result["Bobby Lindamood"]) == 2

    def test_merges_by_last_name_role_and_designation(self):
        """Last-name-only canonical merges when role AND designation match."""
        groups = {
            "Elder": [
                make_llm_person(
                    "Elder", roles=["mayor pro tempore"], designations=["place 1"]
                )
            ],
            "Brandi Elder": [
                make_llm_person(
                    "Brandi Elder",
                    roles=["mayor pro tempore"],
                    designations=["place 1"],
                )
            ],
        }
        result = merge_weak_tie_groups_within_llm(groups)
        assert "Elder" not in result
        assert len(result["Brandi Elder"]) == 2

    def test_no_merge_when_role_differs(self):
        """Same last name but different roles — must not merge."""
        groups = {
            "Smith": [make_llm_person("Smith", roles=["mayor"])],
            "John Smith": [make_llm_person("John Smith", roles=["council member"])],
        }
        result = merge_weak_tie_groups_within_llm(groups)
        assert "Smith" in result
        assert "John Smith" in result

    def test_no_merge_when_designation_differs(self):
        """Same last name and role but different designation — must not merge."""
        groups = {
            "Smith": [
                make_llm_person(
                    "Smith", roles=["council member"], designations=["place 2"]
                )
            ],
            "John Smith": [
                make_llm_person(
                    "John Smith", roles=["council member"], designations=["place 4"]
                )
            ],
        }
        result = merge_weak_tie_groups_within_llm(groups)
        assert "Smith" in result

    def test_no_merge_when_no_roles(self):
        """Last-name-only group with no roles is not merged."""
        groups = {
            "Smith": [make_llm_person("Smith", roles=[])],
            "John Smith": [make_llm_person("John Smith", roles=["mayor"])],
        }
        result = merge_weak_tie_groups_within_llm(groups)
        assert "Smith" in result

    def test_full_name_groups_not_treated_as_weak(self):
        """Two full-name groups sharing a last name are not merged."""
        groups = {
            "Marty C Smith Jr": [make_llm_person("Marty C Smith Jr", roles=["mayor"])],
            "Marty D Smith Sr": [
                make_llm_person("Marty D Smith Sr", roles=["council member"])
            ],
        }
        result = merge_weak_tie_groups_within_llm(groups)
        assert len(result) == 2

    def test_suffix_does_not_confuse_last_name_extraction(self):
        """A last-name-only group still resolves correctly against a suffixed full name."""
        groups = {
            "Smith": [make_llm_person("Smith", roles=["mayor"])],
            "Marty C Smith Jr": [make_llm_person("Marty C Smith Jr", roles=["mayor"])],
        }
        result = merge_weak_tie_groups_within_llm(groups)
        assert "Smith" not in result
        assert len(result["Marty C Smith Jr"]) == 2
