import pytest
from datetime import datetime, timezone
from typing import Dict, List

from domain.models import Person
from jobs.people_collector.steps.step_07_merge_records_across_llms.merge_records_across_llms import (
    merge_records_across_llms,
    group_records_across_llms,
    merge_group_across_llms,
    merge_weak_tie_groups,
    merge_urls,
)
from jobs.people_collector.schemas import (
    WorkflowStatus,
    ProcessPageContentStep,
    MergeRecordsAcrossLLMsStep,
    MergeRecordsWithinLLMStep,
    ResearchMunicipalityStep,
)
from tests.factories.workflow_context import workflow_context_factory

pytestmark = pytest.mark.unit


# --- Fixtures ---

def create_person(
    name: str,
    roles: List[str],
    emails: List[str] = [],
    source_urls: List[str] = [],
    other_names: List[str] = [],
    designations: List[str] = [],
) -> Person:
    return Person(
        name=name,
        other_names=other_names,
        roles=roles,
        designations=designations,
        divisions=["City"] if roles else [],
        emails=emails,
        phones=[],
        urls=[],
        start_date="",
        end_date="",
        image="",
        cdn_image="",
        source_urls=source_urls or ["test_source"],
        jurisdiction_ocdid="test_city",
        updated_at=datetime.now(timezone.utc).isoformat(timespec='seconds'),
    )


def make_context(people_by_llm: Dict[str, List[Person]]):
    return workflow_context_factory({
        WorkflowStatus.MERGE_RECORDS_WITHIN_LLM: MergeRecordsWithinLLMStep(
            people_by_llm=people_by_llm,
        ),
        WorkflowStatus.RESEARCH_MUNICIPALITY: ResearchMunicipalityStep(
            names=[],
            expected_count=0,
        ),
        WorkflowStatus.PROCESS_PAGE_CONTENT: ProcessPageContentStep(
            raw_records_by_llm={},
            records_by_llm={},
        ),
    })


# --- merge_records_across_llms ---

def test_merge_records_across_llms_basic():
    """All people across LLMs should appear in the merged output."""
    people_by_llm = {
        "gpt4": [
            create_person("John Smith", ["Mayor"], ["john@city.gov"], ["city_website"]),
            create_person("Jane Doe", ["Council Member"], ["jane@city.gov"], ["city_website"]),
        ],
        "claude": [
            create_person("John Smith", ["Mayor"], ["john@city.gov"], ["news_article"]),
            create_person("Jane Doe", ["Council Member"], ["jane@city.gov"], ["city_website"]),
        ],
        "gemini": [
            create_person("John Smith", ["Mayor"], ["john.smith@city.gov"], ["government_db"]),
            create_person("Alice Green", ["Treasurer"], ["alice@city.gov"], ["government_db"]),
        ],
    }

    result = merge_records_across_llms(make_context(people_by_llm))

    assert isinstance(result, MergeRecordsAcrossLLMsStep)
    result_names = {p.name for p in result.people}
    assert result_names == {"John Smith", "Jane Doe", "Alice Green"}


def test_merge_records_across_llms_single_llm_person_included():
    """People appearing in only one LLM should still be included."""
    people_by_llm = {
        "gpt4": [create_person("John Smith", ["Mayor"])],
        "claude": [create_person("Solo Person", ["Treasurer"])],
    }

    result = merge_records_across_llms(make_context(people_by_llm))

    result_names = {p.name for p in result.people}
    assert "Solo Person" in result_names


def test_merge_records_across_llms_roles_merged():
    people_by_llm = {
        "gpt4": [create_person("John Smith", ["Mayor"])],
        "claude": [create_person("John Smith", ["Mayor"])],
    }
    result = merge_records_across_llms(make_context(people_by_llm))
    john = next(p for p in result.people if p.name == "John Smith")
    assert "mayor" in john.roles  # roles are normalized to lowercase

def test_merge_records_across_llms_skips_people_with_no_roles():
    """People with no roles after merging should be excluded."""
    people_by_llm = {
        "gpt4": [create_person("No Role Person", [])],
    }

    result = merge_records_across_llms(make_context(people_by_llm))

    result_names = {p.name for p in result.people}
    assert "No Role Person" not in result_names


# --- group_records_across_llms ---

def test_group_exact_name_match():
    """Same name across LLMs should be grouped together."""
    people_by_llm = {
        "llm1": [create_person("Alice", ["A"])],
        "llm2": [create_person("Alice", ["B"])],
    }
    groups = group_records_across_llms({}, people_by_llm)
    assert len(groups) == 1
    assert set(groups[0].keys()) == {"llm1", "llm2"}


def test_group_fuzzy_name_match():
    """Names that fuzzy-match (no conflicting middle names) should be grouped."""
    people_by_llm = {
        "llm1": [create_person("Alex Smith", ["A"])],
        "llm2": [create_person("Alex J. Smith", ["A"])],  # one has middle, one doesn't → fuzzy match
    }
    groups = group_records_across_llms({}, people_by_llm)
    assert len(groups) == 1

def test_group_different_people_not_grouped():
    """People with different names should be in separate groups."""
    people_by_llm = {
        "llm1": [create_person("Alice Jones", ["A"])],
        "llm2": [create_person("Bob Smith", ["B"])],
    }
    groups = group_records_across_llms({}, people_by_llm)
    assert len(groups) == 2


def test_group_identity_alias_match():
    """Names linked via identity config should be grouped together."""
    identity_names = {"John Smith": ["J. Smith"]}
    people_by_llm = {
        "llm1": [create_person("John Smith", ["Mayor"])],
        "llm2": [create_person("J. Smith", ["Mayor"])],
    }
    groups = group_records_across_llms(identity_names, people_by_llm)
    assert len(groups) == 1
    all_names = {p.name for ps in groups[0].values() for p in ps}
    assert all_names == {"John Smith", "J. Smith"}


def test_group_single_llm_forms_own_group():
    """A person from a single LLM should still form their own group."""
    people_by_llm = {
        "llm1": [create_person("Solo Person", ["Treasurer"])],
    }
    groups = group_records_across_llms({}, people_by_llm)
    assert len(groups) == 1
    assert groups[0]["llm1"][0].name == "Solo Person"


def test_group_empty_input():
    groups = group_records_across_llms({}, {"llm1": [], "llm2": []})
    assert groups == []


def test_group_mixed_exact_and_fuzzy():
    people_by_llm = {
        "llm1": [create_person("Bob Idaho", ["A"]), create_person("Alex Smith", ["C"])],
        "llm2": [create_person("Bob Idaho", ["B"]), create_person("Alex J. Smith", ["C"])],
    }
    groups = group_records_across_llms({}, people_by_llm)
    names_per_group = [set(p.name for ps in g.values() for p in ps) for g in groups]
    assert len(groups) == 2
    assert {"Bob Idaho"} in names_per_group
    assert {"Alex Smith", "Alex J. Smith"} in names_per_group

def test_group_mixed_exact_and_fuzzy():
    people_by_llm = {
        "llm1": [create_person("Bob Idaho", ["A"]), create_person("Alex Smith", ["C"])],
        "llm2": [create_person("Bob Idaho", ["B"]), create_person("Alex J. Smith", ["C"])],
    }
    groups = group_records_across_llms({}, people_by_llm)
    names_per_group = [set(p.name for ps in g.values() for p in ps) for g in groups]
    assert len(groups) == 2
    assert {"Bob Idaho"} in names_per_group
    assert {"Alex Smith", "Alex J. Smith"} in names_per_group


# --- merge_group_across_llms ---

def test_merge_group_canonical_name_by_frequency():
    """Most common name in the group should be chosen as canonical."""
    group = [
        create_person("John Smith", ["Mayor"]),
        create_person("John Smith", ["Mayor"]),
        create_person("Jon Smith", ["Mayor"]),
    ]
    merged = merge_group_across_llms(group, "test_city")
    assert merged.name == "John Smith"
    assert "Jon Smith" in merged.other_names


def test_merge_group_combines_other_names():
    """other_names from all group members should be collected and deduplicated."""
    group = [
        Person(name="John Doe", other_names=["J. Doe", "Johnny"], roles=["Mayor"], divisions=[], emails=[], phones=[], urls=[], start_date=None, end_date=None, image=None, cdn_image=None, jurisdiction_ocdid="test", source_urls=["test"], updated_at=""),
        Person(name="Johnny", other_names=["Johnathan Doe"], roles=["Council"], divisions=[], emails=[], phones=[], urls=[], start_date=None, end_date=None, image=None, cdn_image=None, jurisdiction_ocdid="test", source_urls=["test"], updated_at=""),
    ]
    merged = merge_group_across_llms(group, "test")
    assert merged.name == "John Doe"
    assert set(merged.other_names) == {"J. Doe", "Johnny", "Johnathan Doe"}


def test_merge_group_merges_emails():
    group = [
        create_person("Alice", ["Mayor"], emails=["a@city.gov"]),
        create_person("Alice", ["Mayor"], emails=["alice@city.gov"]),
    ]
    merged = merge_group_across_llms(group, "test_city")
    assert set(merged.emails) == {"a@city.gov", "alice@city.gov"}


def test_merge_group_merges_roles():
    group = [
        create_person("Alice", ["Mayor"]),
        create_person("Alice", ["Council Member"]),
    ]
    merged = merge_group_across_llms(group, "test_city")
    assert "mayor" in merged.roles
    assert "council member" in merged.roles

def test_merge_group_source_urls_combined():
    group = [
        create_person("Alice", ["Mayor"], source_urls=["source_a"]),
        create_person("Alice", ["Mayor"], source_urls=["source_b"]),
    ]
    merged = merge_group_across_llms(group, "test_city")
    assert set(merged.source_urls) == {"source_a", "source_b"}

# --- merge_urls ---

def test_merge_urls_prefers_multi_source():
    assert merge_urls([["url_a", "url_b"], ["url_a", "url_c"]]) == ["url_a"]


def test_merge_urls_falls_back_to_single():
    result = merge_urls([["url_a"], ["url_b"]])
    assert len(result) == 1


def test_merge_urls_empty():
    assert merge_urls([]) == []


def test_merge_urls_all_unique_returns_one():
    """When no URL appears more than once, exactly one should be returned."""
    result = merge_urls([["url_a"], ["url_b"], ["url_c"]])
    assert len(result) == 1


# --- merge_weak_tie_groups ---

def make_group(llm_people: Dict[str, List[Person]]) -> Dict[str, List[Person]]:
    return llm_people


class TestMergeWeakTieGroups:
    def test_merges_by_last_name_and_role(self):
        """Last-name-only group merges into full-name group with same role."""
        weak = make_group({"gemini": [create_person("Lindamood", ["mayor"])]})
        strong = make_group({"together_ai": [create_person("Bobby Lindamood", ["mayor"], emails=["b@city.gov"])]})
        result = merge_weak_tie_groups([weak, strong])
        assert len(result) == 1
        people = [p for ps in result[0].values() for p in ps]
        names = {p.name for p in people}
        assert "Bobby Lindamood" in names
        assert "Lindamood" in names

    def test_merges_by_last_name_role_and_designation(self):
        """Last-name-only group merges when role AND designation match."""
        weak = make_group({"gemini": [create_person("Elder", ["mayor pro tempore"], designations=["place 1"])]})
        strong = make_group({"together_ai": [create_person("Brandi Elder", ["mayor pro tempore"], designations=["place 1"])]})
        result = merge_weak_tie_groups([weak, strong])
        assert len(result) == 1

    def test_no_merge_when_role_differs(self):
        """Same last name but different roles — must not merge."""
        weak = make_group({"gemini": [create_person("Smith", ["mayor"])]})
        strong = make_group({"together_ai": [create_person("John Smith", ["council member"])]})
        result = merge_weak_tie_groups([weak, strong])
        assert len(result) == 2

    def test_no_merge_when_designation_differs(self):
        """Same last name and role but different designation — must not merge."""
        weak = make_group({"gemini": [create_person("Smith", ["council member"], designations=["place 2"])]})
        strong = make_group({"together_ai": [create_person("John Smith", ["council member"], designations=["place 4"])]})
        result = merge_weak_tie_groups([weak, strong])
        assert len(result) == 2

    def test_no_merge_when_no_roles(self):
        """Last-name-only group with no roles is not merged."""
        weak = make_group({"gemini": [create_person("Smith", [])]})
        strong = make_group({"together_ai": [create_person("John Smith", ["mayor"])]})
        result = merge_weak_tie_groups([weak, strong])
        assert len(result) == 2

    def test_full_name_groups_not_treated_as_weak(self):
        """Two full-name groups sharing a last name are not merged."""
        group_a = make_group({"llm1": [create_person("Marty C Smith Jr", ["mayor"])]})
        group_b = make_group({"llm2": [create_person("Marty D Smith Sr", ["council member"])]})
        result = merge_weak_tie_groups([group_a, group_b])
        assert len(result) == 2

    def test_suffix_does_not_confuse_last_name_extraction(self):
        """A last-name-only group still resolves correctly against a suffixed full name."""
        weak = make_group({"gemini": [create_person("Smith", ["mayor"])]})
        strong = make_group({"together_ai": [create_person("Marty C Smith Jr", ["mayor"])]})
        result = merge_weak_tie_groups([weak, strong])
        assert len(result) == 1

    def test_weak_group_people_preserved_in_merged_output(self):
        """After merge, the weak group's people exist inside the strong group."""
        weak_person = create_person("Lindamood", ["mayor"])
        strong_person = create_person("Bobby Lindamood", ["mayor"], emails=["b@city.gov"])
        weak = make_group({"gemini": [weak_person]})
        strong = make_group({"together_ai": [strong_person]})
        result = merge_weak_tie_groups([weak, strong])
        all_people = [p for g in result for ps in g.values() for p in ps]
        assert any(p.name == "Lindamood" for p in all_people)
        assert any(p.emails == ["b@city.gov"] for p in all_people)
