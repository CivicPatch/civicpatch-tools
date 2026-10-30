"""Two places reading the same law and asked the same questions share one input hash; any change
to what is read or asked gives a new one."""

from datetime import datetime, timezone

import pytest

from runners.pipeline02_organizations_collector.input_hash import input_hash
from runners.pipeline02_organizations_collector.role_asks import RoleAsk
from runners.pipeline02_organizations_collector.sections import GoverningLawPage, pages_by_kind
from shared.schemas import FoundBy, GoverningLaw, GoverningLawKind
from shared.utils.layered_config import Classification, GovernedBy, GoverningLawConfig

pytestmark = pytest.mark.unit

_STATUTE_URL = "https://legislature.vermont.gov/statutes/fullchapter/24/033"
_STATUTE = GoverningLawPage(id="page-barnard", source_url=_STATUTE_URL, text="§ 2646. Town officers. The legal voters shall elect...")
_VERMONT = GoverningLawConfig(
    charter_terms=["charter"],
    classifications={"town": Classification(governed_by=GovernedBy.CHARTER_OR_GENERAL_LAW, general_law=[_STATUTE_URL])},
)
_LISTER = RoleAsk(organization_name="Board of Listers", role_id="lister", role_label="Lister", names=["Lister", "Listers"])
_CHAIR = RoleAsk(organization_name="Selectboard", role_id="chair", role_label="Chair", names=["Chair"])


def _law(collected_at: datetime, page_ids: list[str], kind: GoverningLawKind = GoverningLawKind.GENERAL_LAW) -> GoverningLaw:
    return GoverningLaw(
        kind=kind,
        classification="town",
        found_by=FoundBy.STATE_INDEX,
        source_page_ids=page_ids,
        collected_at=collected_at,
        cost_usd=None,
    )


_BARNARD_LAW = _law(datetime(2026, 10, 21, tzinfo=timezone.utc), ["page-barnard"])


def _hash(pages=(_STATUTE,), governing_law=_BARNARD_LAW, asks=(_LISTER,), presiding=(_CHAIR,), asks_per_question=2) -> str:
    return input_hash(pages_by_kind(list(pages), governing_law, _VERMONT), list(asks), list(presiding), asks_per_question)


def test_two_towns_reading_one_statute_share_a_hash():
    addison_page = _STATUTE.model_copy(update={"id": "page-addison"})
    addison_law = _law(datetime(2026, 10, 28, tzinfo=timezone.utc), ["page-addison"])

    assert _hash(pages=[addison_page], governing_law=addison_law) == _hash()


def test_a_page_read_as_another_kind_changes_the_hash():
    """A charter place reads any page outside its classification's statute urls as its charter."""
    charter_page = _STATUTE.model_copy(update={"source_url": "https://example.org/charter"})
    charter_law = _BARNARD_LAW.model_copy(update={"kind": GoverningLawKind.CHARTER})

    assert _hash(pages=[charter_page], governing_law=charter_law) != _hash(pages=[charter_page])


@pytest.mark.parametrize(
    "changes",
    [
        {"pages": [_STATUTE.model_copy(update={"text": _STATUTE.text + " Amended."})]},
        {"pages": [_STATUTE.model_copy(update={"source_url": "https://example.org/statute"})]},
        {"asks": [_LISTER.model_copy(update={"role_label": "Board of Listers member"})]},
        {"asks": [_LISTER.model_copy(update={"names": ["Lister"]})]},
        {"presiding": []},
        {"asks_per_question": 3},
    ],
    ids=["page text", "page url", "question", "names", "presiding", "asks per question"],
)
def test_a_change_to_what_is_read_or_asked_changes_the_hash(changes):
    assert _hash(**changes) != _hash()
