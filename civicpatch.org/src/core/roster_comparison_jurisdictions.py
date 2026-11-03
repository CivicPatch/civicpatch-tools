"""Each incoming row's jurisdiction, among the state's at the upload's level: its ocdid decides alone; without
one, its geoid and name must point to one. Anything else is refused for the user, with what its values point to."""

from shared.utils.name_utils import normalize_text_for_search

from core.organization_derivation import LEGAL_STATUS_WORDS
from core.sheet_import_rows import normalize_geoid
from schemas.jurisdictions import StateJurisdiction
from schemas.roster_comparisons import IncomingRow, RejectedReason, RejectedRow, UploadedRow

FILLER_WORDS = frozenset({"of", "the"})


def resolve_rows(
    rows: list[IncomingRow], jurisdictions: list[StateJurisdiction], state: str
) -> tuple[list[UploadedRow], list[RejectedRow]]:
    results = [resolve_row(row, jurisdictions, state) for row in rows]
    resolved = [result for result in results if isinstance(result, UploadedRow)]
    rejected = [result for result in results if isinstance(result, RejectedRow)]
    return resolved, rejected


def ocdids_of(jurisdictions: list[StateJurisdiction]) -> set[str]:
    return {jurisdiction.jurisdiction_ocdid for jurisdiction in jurisdictions}


def resolve_row(row: IncomingRow, jurisdictions: list[StateJurisdiction], state: str) -> UploadedRow | RejectedRow:
    ocdid = row.jurisdiction_ocdid
    if not ocdid:
        return _by_geoid_and_name(row, jurisdictions)
    if any(jurisdiction.jurisdiction_ocdid == ocdid for jurisdiction in jurisdictions):
        return _resolved_row(row, ocdid)
    return _rejected(row, _reason_for_unknown_ocdid(ocdid, state), [])


def _reason_for_unknown_ocdid(ocdid: str, state: str) -> RejectedReason:
    if f"state:{state}" in ocdid.split("/"):
        return RejectedReason.UNKNOWN_JURISDICTION
    return RejectedReason.OUTSIDE_STATE


def _by_geoid_and_name(row: IncomingRow, jurisdictions: list[StateJurisdiction]) -> UploadedRow | RejectedRow:
    by_geoid = _with_geoid(row.geoid or "", jurisdictions)
    name = row.jurisdiction_name or ""
    by_name = _with_name(name, jurisdictions)
    if row.geoid and not by_geoid:
        return _rejected(row, RejectedReason.UNKNOWN_GEOID, by_name)
    if name and not by_name:
        same_name = _with_same_name(name, jurisdictions)
        others = [jurisdiction for jurisdiction in by_geoid if jurisdiction not in same_name]
        return _rejected(row, RejectedReason.UNKNOWN_NAME, [*same_name, *others])
    if not (row.geoid and name):
        return _the_only_one(row, by_geoid or by_name)
    in_both =[jurisdiction for jurisdiction in by_geoid if jurisdiction in by_name]
    if not in_both:
        return _rejected(row, RejectedReason.AMBIGUOUS, [*by_geoid, *by_name])
    return _the_only_one(row, in_both)


def _the_only_one(row: IncomingRow, candidates: list[StateJurisdiction]) -> UploadedRow | RejectedRow:
    if len(candidates) == 1:
        return _resolved_row(row, candidates[0].jurisdiction_ocdid)
    return _rejected(row, RejectedReason.AMBIGUOUS, candidates)


def _with_geoid(geoid: str, jurisdictions: list[StateJurisdiction]) -> list[StateJurisdiction]:
    # Blank after normalizing would otherwise match every jurisdiction with no geoid.
    wanted = normalize_geoid(geoid)
    if not wanted:
        return []
    return [jurisdiction for jurisdiction in jurisdictions if normalize_geoid(jurisdiction.geoid) == wanted]


def _with_name(name: str, jurisdictions: list[StateJurisdiction]) -> list[StateJurisdiction]:
    """Barre fits Barre city and Barre town; Barre City only the city; Fayston City not Fayston town."""
    same_name = _with_same_name(name, jurisdictions)
    return [jurisdiction for jurisdiction in same_name if _types_agree(name, jurisdiction.name)]


def _with_same_name(name: str, jurisdictions: list[StateJurisdiction]) -> list[StateJurisdiction]:
    wanted = _distinguishing_words(name)
    if not wanted:
        return []
    return [jurisdiction for jurisdiction in jurisdictions if _distinguishing_words(jurisdiction.name) == wanted]


def _types_agree(name: str, jurisdiction_name: str) -> bool:
    """Types conflict only when both names state one."""
    types = _type_words(name)
    jurisdiction_types = _type_words(jurisdiction_name)
    if not types or not jurisdiction_types:
        return True
    return bool(types & jurisdiction_types)


def _distinguishing_words(name: str) -> list[str]:
    """Town of Fayston and Fayston town are both just fayston."""
    return [word for word in _words(name) if word not in LEGAL_STATUS_WORDS and word not in FILLER_WORDS]


def _type_words(name: str) -> set[str]:
    return {word for word in _words(name) if word in LEGAL_STATUS_WORDS}


def _words(name: str) -> list[str]:
    # The search normalizer deletes punctuation, which would make "Winston-Salem" one word.
    return normalize_text_for_search(name.replace("-", " ")).split()


def _resolved_row(row: IncomingRow, ocdid: str) -> UploadedRow:
    return UploadedRow.model_validate({**row.model_dump(), "jurisdiction_ocdid": ocdid})


def _rejected(row: IncomingRow, reason: RejectedReason, candidates: list[StateJurisdiction]) -> RejectedRow:
    return RejectedRow(
        source_row=row.source_row,
        jurisdiction_ocdid=row.jurisdiction_ocdid,
        geoid=row.geoid,
        jurisdiction_name=row.jurisdiction_name,
        reason=reason,
        candidates=candidates,
    )
