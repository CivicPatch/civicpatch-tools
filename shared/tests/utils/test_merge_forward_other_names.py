"""`merge_forward_other_names` — why a scrape must not clobber human-added aliases.

Moved from the pipeline's step 07 with the function on 2026-08-21; cp.org calls it now that
it resolves identity at ingest.
"""

from shared.utils.person_id_utils import merge_forward_other_names


# Guard: human-confirmed aliases live in `other_names` and are the durable signal
# that steers next-run matching. Ingest must carry the matched entity's
# existing aliases forward, or each run clobbers them. See the identity-resolution plan.


def test_merge_forward_preserves_existing_human_aliases():
    result = merge_forward_other_names(
        person_name="Bob Smith",
        person_other_names=[],
        existing_name="Robert Smith",
        existing_other_names=["Bobby"],  # a human-added alias on the entity
    )
    assert "Bobby" in result  # the guard: existing alias survives
    assert "Robert Smith" in result  # renamed → old name kept as alias
    assert "Bob Smith" in result  # new name folded in too


def test_merge_forward_carries_aliases_even_when_name_unchanged():
    # Same scraped name → no name variants added, but existing aliases still merge.
    result = merge_forward_other_names(
        person_name="Robert Smith",
        person_other_names=["Rob"],
        existing_name="Robert Smith",
        existing_other_names=["Bobby"],
    )
    assert result == ["Rob", "Bobby"]


def test_merge_forward_dedupes_and_preserves_order():
    result = merge_forward_other_names(
        person_name="Bob",
        person_other_names=["Rob"],
        existing_name="Robert",
        existing_other_names=["Rob", "Robert"],
    )
    assert result == ["Rob", "Bob", "Robert"]


def test_merge_forward_no_existing_match_is_a_noop():
    result = merge_forward_other_names(
        person_name="Bob",
        person_other_names=["Rob"],
        existing_name=None,
        existing_other_names=[],
    )
    assert result == ["Rob"]
