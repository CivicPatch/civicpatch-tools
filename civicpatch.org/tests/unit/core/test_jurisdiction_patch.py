import pytest

from core.jurisdiction_patch import (
    apply_patch,
    build_patch,
    current_values,
    find_jurisdiction,
    patch_is_live,
)


@pytest.mark.unit
class TestPatchIsLive:
    def test_true_when_every_requested_field_matches(self):
        assert patch_is_live({"url": "https://x.gov"}, {"url": "https://x.gov", "geoid": "1"})

    def test_false_when_a_field_has_not_landed(self):
        assert not patch_is_live({"url": "https://x.gov"}, {"url": "https://old.gov"})

    def test_false_when_only_some_of_the_patch_landed(self):
        assert not patch_is_live(
            {"url": "https://x.gov", "geoid": "2"}, {"url": "https://x.gov", "geoid": "1"}
        )

    def test_ignores_fields_the_edit_did_not_ask_for(self):
        assert patch_is_live({"url": "https://x.gov"}, {"url": "https://x.gov", "population": 5})

    def test_empty_patch_never_counts_as_landed(self):
        # Otherwise a malformed request would resolve itself on the first sync.
        assert not patch_is_live({}, {"url": "https://x.gov"})


@pytest.mark.unit
class TestBuildPatch:
    def test_drops_absent_fields_so_they_are_left_alone(self):
        # None must never mean "clear it" — that is the overwrite bug this replaces.
        assert build_patch({"url": "https://x.gov", "geoid": None}) == {"url": "https://x.gov"}

    def test_ignores_fields_that_are_not_patchable(self):
        assert build_patch({"url": "https://x.gov", "name": "Nope"}) == {"url": "https://x.gov"}


@pytest.mark.unit
class TestApplyPatch:
    DOC = {"jurisdictions": [{"id": "a", "url": "old"}, {"id": "b", "url": "keep"}]}

    def test_patches_only_the_named_entry(self):
        out = apply_patch(self.DOC, "a", {"url": "new"})
        assert out["jurisdictions"] == [{"id": "a", "url": "new"}, {"id": "b", "url": "keep"}]

    def test_leaves_the_original_untouched(self):
        # The caller still reads pre-edit values off the original for the change log.
        apply_patch(self.DOC, "a", {"url": "new"})
        assert self.DOC["jurisdictions"][0]["url"] == "old"

    def test_current_values_reports_the_before_side(self):
        entry = find_jurisdiction(self.DOC, "a")
        assert current_values(entry, {"url": "new"}) == {"url": "old"}
