"""The saved rows are YAML, so every field has to be something YAML can write.

`organization_placed_by` is a `StrEnum`: dumped as the enum member it raises
`RepresenterError: cannot represent an object`, which ended a prod run at save time.
"""

from shared.schemas import PersonSourceRecord
from shared.utils.statuses import OrganizationPlacedBy

from runners.pipeline03_people_collector.steps.step_05_save_output.save_output import (
    save_data_to_file,
)


def test_a_placed_record_saves_its_stem_as_its_value(tmp_path):
    path = tmp_path / "roster.yml"

    save_data_to_file(
        [
            PersonSourceRecord(
                name="Ann Lee",
                label="Town Clerk",
                source_url="https://townofgeorgia.com/clerk",
                organization_placed_by=OrganizationPlacedBy.ROLE,
            )
        ],
        str(path),
    )

    assert "organization_placed_by: role" in path.read_text()


def test_an_unplaced_record_saves_a_null_stem(tmp_path):
    path = tmp_path / "roster.yml"

    save_data_to_file(
        [PersonSourceRecord(name="Bo Ray", label="Chair", source_url="https://townofgeorgia.com/sb")],
        str(path),
    )

    assert "organization_placed_by: null" in path.read_text()
