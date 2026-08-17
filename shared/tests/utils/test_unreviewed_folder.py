"""unreviewed_folder — where a scrape lands before a human has approved it.

The unreviewed copy is a sibling of the reviewed level (`local` -> `local-unreviewed`) so the
two sit side by side in open-data. Keeping it inside `data/` means it matches the sync's
people-file shape, which is why `classify_path` excludes it explicitly.
"""

import pytest

from shared.utils.id_utils import jurisdiction_ocdid_to_folder, unreviewed_folder


@pytest.mark.unit
def test_suffixes_the_level_segment():
    assert unreviewed_folder("wa/local/place_seattle") == "wa/local-unreviewed/place_seattle"


@pytest.mark.unit
def test_leaves_state_and_place_untouched():
    folder = unreviewed_folder("il/local/county_dupage__place_naperville")
    assert folder == "il/local-unreviewed/county_dupage__place_naperville"


@pytest.mark.unit
def test_composes_with_the_folder_builder():
    """The real caller builds the folder from an ocdid, so pin the two together."""
    ocdid = "ocd-jurisdiction/country:us/state:wa/place:seattle/government"
    assert unreviewed_folder(jurisdiction_ocdid_to_folder(ocdid)) == (
        "wa/local-unreviewed/place_seattle"
    )


@pytest.mark.unit
def test_rejects_a_state_only_folder():
    """A state-only ocdid has no level segment, so there is nothing to mark unreviewed —
    suffixing the state would write to a different state's tree."""
    with pytest.raises(ValueError):
        unreviewed_folder("tx")
