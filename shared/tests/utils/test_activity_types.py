"""Every activity type is classified as changing published data or not.

The outward mirrors sweep on `PUBLISHED_CHANGE_TYPES` alone. A type left out of both sets would
be neither swept nor deliberately skipped — `SHEET_IMPORT` once leaked into open-data commits
that credited unpublished imports because the sweep was a denylist.
"""

import pytest

from shared.utils.statuses import PUBLISHED_CHANGE_TYPES, UNPUBLISHED_ACTIVITY_TYPES, ActivityType

pytestmark = pytest.mark.unit


def test_every_activity_type_is_classified():
    assert PUBLISHED_CHANGE_TYPES | UNPUBLISHED_ACTIVITY_TYPES == set(ActivityType)


def test_no_activity_type_is_both():
    assert not PUBLISHED_CHANGE_TYPES & UNPUBLISHED_ACTIVITY_TYPES


def test_proposals_are_not_published_changes():
    for proposal in (ActivityType.SHEET_IMPORT, ActivityType.PIPELINE_RUN_END):
        assert proposal not in PUBLISHED_CHANGE_TYPES
