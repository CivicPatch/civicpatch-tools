"""Pure — the open-data commit body. No mocks."""

import pytest

from core.sinks.open_data_commit import ChangesetAttribution, commit_body
from shared.utils.statuses import ChangesetKind

_BERKELEY = "ocd-jurisdiction/country:us/state:ca/place:berkeley/government"
_COVINA = "ocd-jurisdiction/country:us/state:ca/place:covina/government"


def _attribution(changeset_id: str, **fields) -> ChangesetAttribution:
    return ChangesetAttribution(
        changeset_id=changeset_id,
        kind=fields.get("kind", ChangesetKind.SCRAPE),
        published_by=fields.get("published_by", "mango"),
        batch_id=fields.get("batch_id"),
    )


@pytest.mark.unit
def test_names_the_kind_changeset_publisher_and_batch():
    attributions = {
        "c1": _attribution("c1", kind=ChangesetKind.SHEET_IMPORT, batch_id="b1"),
    }

    assert commit_body({_BERKELEY: ["c1"]}, attributions) == (
        f"{_BERKELEY}: sheet_import c1 by mango (batch b1)"
    )


@pytest.mark.unit
def test_one_line_per_jurisdiction_in_ocdid_order():
    attributions = {"c1": _attribution("c1"), "c2": _attribution("c2")}

    body = commit_body({_COVINA: ["c2"], _BERKELEY: ["c1"]}, attributions)

    assert body.splitlines() == [
        f"{_BERKELEY}: scrape c1 by mango",
        f"{_COVINA}: scrape c2 by mango",
    ]


@pytest.mark.unit
def test_several_changesets_share_a_line():
    attributions = {"c1": _attribution("c1"), "c2": _attribution("c2", published_by="bob")}

    assert commit_body({_BERKELEY: ["c2", "c1"]}, attributions) == (
        f"{_BERKELEY}: scrape c1 by mango; scrape c2 by bob"
    )


@pytest.mark.unit
def test_a_changeset_that_was_not_published_is_not_named():
    """The sweep's feed also carries open imports and dismissed runs; the query leaves them out."""
    assert commit_body({_BERKELEY: ["open-import"]}, {}) == _BERKELEY


@pytest.mark.unit
def test_no_publisher_leaves_out_the_by():
    attributions = {"c1": _attribution("c1", published_by=None)}

    assert commit_body({_BERKELEY: ["c1"]}, attributions) == f"{_BERKELEY}: scrape c1"
