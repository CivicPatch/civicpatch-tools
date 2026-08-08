"""Reads meaning out of open-data repo paths. Pure — no I/O, no repo access.

The sync only cares about two path shapes:

    data_source/<state>/<level>/jurisdictions.yml   the list of jurisdictions for one
                                                    (state, level) slice
    data/<state>/<level>/<place>.yml                the people for one jurisdiction

Everything else in the repo (READMEs, jurisdictions_metadata.yml, validation output,
scripts) is not synced. This module answers three questions about a path: what kind of
file is it, which (state, level) does it belong to, and in what order should levels sync.
"""

from enum import StrEnum

from shared.schemas import JurisdictionLevel
from shared.utils.id_utils import parse_jurisdiction_ocdid

# Dependent levels are built from their state's stored row, so state syncs first.
# Unknown levels sort last — they can sync, but nothing may depend on them.
LEVEL_SYNC_ORDER = (
    JurisdictionLevel.STATE,
    JurisdictionLevel.COUNTIES,
    JurisdictionLevel.LOCAL,
)


class SyncFileKind(StrEnum):
    JURISDICTIONS = "jurisdictions"
    PEOPLE = "people"


def classify_path(path: str) -> SyncFileKind | None:
    if (
        path.startswith("data_source/")
        and path.endswith("/jurisdictions.yml")
        and path.count("/") == 3
    ):
        return SyncFileKind.JURISDICTIONS
    if path.startswith("data/") and path.endswith(".yml") and path.count("/") == 3:
        return SyncFileKind.PEOPLE
    return None


def jurisdiction_path_parts(path: str) -> tuple[str, str]:
    # data_source/<state>/<level>/jurisdictions.yml
    parts = path.split("/")
    return parts[1], parts[2]


def jurisdictions_file_path(jurisdiction_ocdid: str) -> str:
    # Which list file this jurisdiction is defined in.
    parsed = parse_jurisdiction_ocdid(jurisdiction_ocdid)
    return f"data_source/{parsed.state}/{parsed.level}/jurisdictions.yml"


def level_ordered_batches(paths: list[str]) -> list[list[str]]:
    by_level: dict[str, list[str]] = {}
    for path in paths:
        _state, level = jurisdiction_path_parts(path)
        by_level.setdefault(level, []).append(path)

    ordered = [level for level in LEVEL_SYNC_ORDER if level in by_level]
    ordered += sorted(level for level in by_level if level not in LEVEL_SYNC_ORDER)
    return [by_level[level] for level in ordered]
