import pytest

from runners.people_collector.schemas import LinkStatus
from tests.prompts.tests.evals.generate_relevance_cases import (
    Candidate,
    SavedPage,
    SavedRun,
    candidate_cases,
    candidate_for,
    case_id,
)

pytestmark = pytest.mark.unit

DONE = LinkStatus.DONE.value
IRRELEVANT = LinkStatus.PROCESSED_IRRELEVANT.value


def test_a_cited_page_is_relevant():
    assert candidate_for(DONE, cited=True) is Candidate.RELEVANT


def test_a_cited_page_the_model_rejected_is_relevant_and_flagged():
    assert candidate_for(IRRELEVANT, cited=True) is Candidate.RELEVANT_MODEL_DISAGREED


def test_an_uncited_page_the_model_accepted_is_a_negative_to_review():
    assert candidate_for(DONE, cited=False) is Candidate.IRRELEVANT_TO_REVIEW


def test_a_page_both_sides_reject_is_skipped():
    assert candidate_for(IRRELEVANT, cited=False) is None


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
    assert candidate_cases(_run(("https://x.gov/council", DONE)), cited=set(), known=set()) == []


def test_a_page_already_in_the_dataset_is_not_proposed_again():
    run = _run(("https://www.x.gov/Council/", DONE))

    cases = candidate_cases(run, cited={"https://x.gov/council"}, known={"https://x.gov/council"})

    assert cases == []


def test_cited_and_disputed_pages_become_cases_and_agreed_rejections_do_not():
    run = _run(
        ("https://x.gov/council", DONE),
        ("https://x.gov/parks", IRRELEVANT),
        ("https://x.gov/news", DONE),
    )

    cases = candidate_cases(run, cited={"https://x.gov/council"}, known=set())

    assert [(c.page_url, c.candidate) for c in cases] == [
        ("https://x.gov/council", Candidate.RELEVANT),
        ("https://x.gov/news", Candidate.IRRELEVANT_TO_REVIEW),
    ]
