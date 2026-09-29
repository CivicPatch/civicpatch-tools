import pytest

from runners.people_collector.schemas import LinkStatus
from tests.prompts.tests.evals.generate_relevance_cases import (
    Candidate,
    PromptInputs,
    SavedPage,
    SavedRun,
    candidate_cases,
    candidate_for,
    case_id,
    prompt_inputs,
)
from shared.utils.government_forms import load_government_forms_config

pytestmark = pytest.mark.unit

DONE = LinkStatus.DONE.value
IRRELEVANT = LinkStatus.PROCESSED_IRRELEVANT.value
NO_FORM = PromptInputs(government_form=None, known_roles=[], known_organizations=["Government"])


def test_a_cited_page_is_relevant():
    assert candidate_for(DONE, cited=True) is Candidate.RELEVANT


def test_a_cited_page_the_model_rejected_is_relevant_and_flagged():
    assert candidate_for(IRRELEVANT, cited=True) is Candidate.RELEVANT_MODEL_DISAGREED


def test_an_uncited_page_the_model_accepted_is_proposed_relevant():
    assert candidate_for(DONE, cited=False) is Candidate.RELEVANT_UNCITED


def test_a_page_both_sides_reject_is_a_negative():
    assert candidate_for(IRRELEVANT, cited=False) is Candidate.IRRELEVANT


def test_a_page_the_model_never_judged_is_skipped():
    assert candidate_for(LinkStatus.PENDING.value, cited=True) is None


def test_case_ids_are_folder_safe():
    input_path = "data_source/ma/local/x/cache/www_x_gov_m_directory_employee?eid=254/preprocessed.md"

    assert case_id("county_worcester__place_millbury", input_path) == (
        "county_worcester__place_millbury__www_x_gov_m_directory_employee_eid_254"
    )


def _run(*pages: tuple[str, str]) -> SavedRun:
    return SavedRun(
        folder="place_x",
        jurisdiction_ocdid="ocd-jurisdiction/country:us/state:wa/place:x/government",
        jurisdiction_name="X city",
        pages=[
            SavedPage(url=url, status=status, input_path=f"cache/{i}/preprocessed.md")
            for i, (url, status) in enumerate(pages)
        ],
    )


def test_a_jurisdiction_with_no_published_roster_proposes_nothing():
    assert candidate_cases(_run(("https://x.gov/council", DONE)), cited=set(), known=set(), inputs=NO_FORM) == []


def test_a_page_already_in_the_dataset_is_not_proposed_again():
    run = _run(("https://www.x.gov/Council/", DONE))

    cases = candidate_cases(
        run, cited={"https://x.gov/council"}, known={"https://x.gov/council"}, inputs=NO_FORM
    )

    assert cases == []


def test_every_judged_page_becomes_a_case():
    run = _run(
        ("https://x.gov/council", DONE),
        ("https://x.gov/parks", IRRELEVANT),
        ("https://x.gov/news", DONE),
    )

    cases = candidate_cases(run, cited={"https://x.gov/council"}, known=set(), inputs=NO_FORM)

    assert [(c.page_url, c.candidate) for c in cases] == [
        ("https://x.gov/council", Candidate.RELEVANT),
        ("https://x.gov/parks", Candidate.IRRELEVANT),
        ("https://x.gov/news", Candidate.RELEVANT_UNCITED),
    ]


def test_at_most_two_of_each_label_per_jurisdiction():
    run = _run(*[(f"https://x.gov/member-{i}", DONE) for i in range(4)], *[(f"https://x.gov/news-{i}", IRRELEVANT) for i in range(4)])

    cases = candidate_cases(run, cited={"https://x.gov/council"}, known=set(), inputs=NO_FORM)

    assert [c.candidate for c in cases] == [Candidate.RELEVANT_UNCITED] * 2 + [Candidate.IRRELEVANT] * 2


def _run_in(jurisdiction_ocdid: str, name: str) -> SavedRun:
    return SavedRun(folder="x", jurisdiction_ocdid=jurisdiction_ocdid, jurisdiction_name=name, pages=[])


def test_a_rule_decided_form_gives_production_its_organizations_and_roles():
    config = load_government_forms_config()
    run = _run_in("ocd-jurisdiction/country:us/state:mi/place:mikado/government", "Mikado township")

    inputs = prompt_inputs(config, run)

    assert inputs.government_form == "township_board"
    assert inputs.known_organizations == ["Board"]
    assert inputs.known_roles == ["Supervisor", "Clerk", "Treasurer", "Trustee"]


def test_no_form_gives_the_default_organization_and_no_roles():
    config = load_government_forms_config()
    run = _run_in("ocd-jurisdiction/country:us/state:wa/place:seattle/government", "Seattle city")

    assert prompt_inputs(config, run) == NO_FORM


def test_a_county_with_no_form_yet_gets_its_states_board():
    config = load_government_forms_config()
    run = _run_in("ocd-jurisdiction/country:us/state:wa/county:king/government", "King County")

    inputs = prompt_inputs(config, run)

    assert inputs.government_form is None
    assert inputs.known_organizations == ["Board of County Commissioners"]
    assert inputs.known_roles == ["Commissioner", "Chair"]
