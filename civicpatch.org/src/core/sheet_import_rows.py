"""The import sheet's rows in: a spreadsheet row becomes the sighting `source_records` stores.

What goes back out — each row's status, error and note — is `sheet_import_columns`. Pure: the
Sheets calls are the caller's. Which sheet and which tabs is `services.entry_sheet`. Spec:
`.scratch/2026-08-25-sheet-import-shape.md`.

The sheet carries no ids — matching is ingest's job, so there is nowhere to paste a uuid wrong.
One row is one sighting; `roster_from_rows` groups by name, so two rows for one person would
invite "Bob Smith" and "Robert Smith" to become two people.

Which town a row belongs to is answered in order: `jurisdiction_ocdid` typed or pasted directly,
else the jurisdiction its `geoid` names, else the one whose website `source_url` is on
(`core.source_sites`). A site that matches none, or several, is a row error asking for either id.
"""

from enum import StrEnum

from pydantic import BaseModel

from core.source_sites import SiteIndex, jurisdictions_on_site, organization_on_site, site_host
from shared.utils.email_utils import is_valid_email
from shared.utils.phone_utils import normalize_phone_number
from shared.utils.url_utils import is_web_url

JURISDICTION = "jurisdiction_ocdid"
GEOID = "geoid"

# Written by the import, never by a volunteer. Every row gets a value on every run: a row that
# failed last time and is fine now must not keep last time's message.
STATUS_COLUMNS = ("status", "error", "last_import_at", "note")

class ImportStatus(StrEnum):
    """What a whole jurisdiction's `status` can say. Coarser than a row's: a town is the unit
    that succeeds or fails, because a town is the unit that gets imported."""

    IMPORTED = "imported"
    # People stored, posts not. Re-derivable from the sightings, so not a failure.
    PARTIAL = "partial"
    FAILED = "failed"
    # The sheet says exactly what it said last run, so no card was raised.
    UNCHANGED = "unchanged"


_REQUIRED = ("name", "source_url")
# A blank cell states nothing: the published value is kept (`people_roster.partial_roster`). A blank
# `label` keeps the person's current post; for someone new it derives to unmatched. `other_names`
# only ever adds: a name left out is not taken away.
_OPTIONAL = ("label", "email", "phone", "image", "other_names")

# The Live tabs' list separator. Not a comma: a name can hold one ("Hale, Jr.").
NAMES_SEPARATOR = " | "


class RowError(BaseModel):
    """A problem with one row, as data — reported, never raised.

    Carries its jurisdiction because a rejected row never becomes an `ImportRow`, and the
    importer blocks per jurisdiction: without this there is nothing to attribute it to.
    """

    # None for a jurisdiction that failed during ingest rather than a row the sheet rejected.
    line: int | None
    jurisdiction_ocdid: str
    column: str | None
    message: str


class Sighting(BaseModel):
    """Exactly what `insert_source_records` writes, keyed as `source_records` names it."""

    name: str
    other_names: list[str] = []
    label: str
    source_url: str
    # The body whose site `source_url` is on; None for the jurisdiction's default.
    organization_id: str | None = None
    url: str | None = None
    phone: str | None = None
    email: str | None = None
    image: str | None = None
    start_date: str | None = None
    end_date: str | None = None


class ImportRow(BaseModel):
    line: int
    jurisdiction_ocdid: str
    sighting: Sighting
    # What the last run wrote here. Blank for a row nobody has imported, and blank again when a
    # volunteer clears it to say "look at this one again".
    status: str = ""
    # Blank unless an id the row gave was passed over; see `jurisdiction_note`.
    jurisdiction_note: str = ""


def clean_cell(value) -> str:
    """A sheet cell as text, trimmed; blank for an empty one."""
    return "" if value is None else str(value).strip()


def _optional(value) -> str | None:
    return clean_cell(value) or None


def _names(value) -> list[str]:
    """Split on the bare bar, so "a|b" reads the same as "a | b"."""
    names = clean_cell(value).split(NAMES_SEPARATOR.strip())
    return [name.strip() for name in names if name.strip()]


def normalize_geoid(value) -> str:
    """Leading zeros dropped, so a text cell ("0601514") and the number Sheets reads that same
    cell as (601514) land on the same key. Lossless: no state is `00`, so county, place and
    cousub geoids still cannot collide once stripped."""
    return clean_cell(value).lstrip("0")


class JurisdictionIndex(BaseModel):
    """Every active jurisdiction, under both ids a row can name one with."""

    ocdids: set[str] = set()
    by_geoid: dict[str, str] = {}


def build_jurisdiction_index(geoids_by_ocdid: dict[str, str | None]) -> JurisdictionIndex:
    """Geoids re-keyed the way `normalize_geoid` reads a cell, so both sides of the lookup are
    normalized by the same function and cannot drift.

    A geoid that normalizes to blank is dropped: it would key on what an empty cell resolves to,
    quietly filing every row that named no jurisdiction under that one town.
    """
    by_geoid = {}
    for ocdid, geoid in geoids_by_ocdid.items():
        bare = normalize_geoid(geoid)
        if bare:
            by_geoid[bare] = ocdid
    return JurisdictionIndex(ocdids=set(geoids_by_ocdid), by_geoid=by_geoid)


def resolve_jurisdiction(row: dict, sites: SiteIndex, jurisdictions: JurisdictionIndex) -> str:
    """The first id the row gives that names a jurisdiction we hold, else the one whose site its
    source is on, else blank.

    An id naming nothing is passed over, not trusted: a typo in the ocdid would otherwise beat a
    geoid that was right. What was passed over is reported by `jurisdiction_note`.
    """
    typed = clean_cell(row.get(JURISDICTION))
    if typed in jurisdictions.ocdids:
        return typed
    named = jurisdictions.by_geoid.get(normalize_geoid(row.get(GEOID)))
    if named:
        return named
    matches = jurisdictions_on_site(sites, clean_cell(row.get("source_url")))
    return matches[0] if len(matches) == 1 else ""


def _handled_jurisdictions(
    rows: list[dict], sites: SiteIndex, jurisdictions: JurisdictionIndex
) -> set[str]:
    """Every jurisdiction whose rows all already carry a status — on the unvalidated row, since
    this runs before a row is known to parse at all.

    Whole, not row by row: a town where every row already says `imported` is genuinely
    unchanged, but a town with one cleared row among ten `imported` ones is not — clearing one
    row is how a volunteer asks for the whole town again (`ImportRow`-level `already_handled`
    documents the same rule downstream, on rows that did parse).
    """
    by_jurisdiction: dict[str, list[dict]] = {}
    for row in rows:
        if _is_blank(row):
            continue
        by_jurisdiction.setdefault(resolve_jurisdiction(row, sites, jurisdictions), []).append(row)
    return {
        jurisdiction
        for jurisdiction, jurisdiction_rows in by_jurisdiction.items()
        if all(clean_cell(row.get("status")) for row in jurisdiction_rows)
    }


def parse_rows(
    rows: list[dict], sites: SiteIndex, jurisdictions: JurisdictionIndex
) -> tuple[list[ImportRow], list[RowError]]:
    """Every row that parsed, and every reason one did not.

    Line numbers count the header, so they match the row gutter a volunteer sees.
    """
    parsed: list[ImportRow] = []
    errors: list[RowError] = []

    handled = _handled_jurisdictions(rows, sites, jurisdictions)
    for offset, row in enumerate(rows):
        line = offset + 2
        # A row with nothing in it is grid, not a row somebody wrote. Sheets returns every line
        # in the used range, so a tab with 4 entries and 140 spare lines otherwise reports 420
        # "required" errors and blocks the import on rows nobody typed.
        if _is_blank(row):
            continue
        # Already handled — clearing a row's status is how a volunteer asks for it again, and
        # doing that on any one row brings the whole town back (see `_handled_jurisdictions`).
        # Skipped before validation, not just before import: a row that fails validation never
        # becomes an `ImportRow`, so the existing jurisdiction-level "all handled" check
        # (`already_handled`, in `services.sheet_import`) never even sees it — and a contract
        # change made after the row was accepted (a new required column, say) would otherwise
        # re-reject a row nothing is wrong with, forever, on every run.
        jurisdiction = resolve_jurisdiction(row, sites, jurisdictions)
        if jurisdiction in handled:
            continue
        row_errors = _row_errors(row, line, jurisdiction, sites)
        if row_errors:
            errors.extend(row_errors)
        else:
            parsed.append(_import_row(row, line, jurisdiction, sites, jurisdictions))

    return parsed, errors + _duplicate_errors(parsed)


# What a volunteer fills in. `STATUS_COLUMNS` are ours and deliberately excluded below.
# The two jurisdiction ids lead, in the order they resolve.
_VOLUNTEER_COLUMNS = (JURISDICTION, GEOID) + _REQUIRED + _OPTIONAL

# Public: `services.sheet_import` marks these on the sheet itself, so a required column reads
# as required without anyone having to already know the contract.
REQUIRED_COLUMNS = _REQUIRED

# Ours and never read back: the aliases the row's person is already published with, beside
# `other_names` so a volunteer adds only what is missing.
PUBLISHED_OTHER_NAMES = "published_other_names"

# The header row in full — the single source of truth `services.sheet_import` writes to the
# sheet itself, so the contract can never drift from what this module actually reads.
ROSTER_HEADERS = _VOLUNTEER_COLUMNS + (PUBLISHED_OTHER_NAMES,) + STATUS_COLUMNS


def _is_blank(row: dict) -> bool:
    """Whether the volunteer typed anything on this line.

    App-owned columns do not count. The write-back used to stamp `last_import_at` down the whole
    used range, so a spare line can carry a timestamp and still be a line nobody wrote — judging
    on every value would call it occupied and reject it three times over.
    """
    return not any(clean_cell(row.get(column)) for column in _VOLUNTEER_COLUMNS)


def _site_error(row: dict, jurisdiction: str, sites: SiteIndex) -> str | None:
    """Why a row that resolved to no jurisdiction could not take one from its source's site.

    Judged on the resolved jurisdiction, not on the ocdid cell: a row a geoid answered has its
    town already, and a site matching none or several says nothing about it.
    """
    source_url = clean_cell(row.get("source_url"))
    if jurisdiction or not source_url:
        return None
    matches = jurisdictions_on_site(sites, source_url)
    host = site_host(source_url)
    ask = f"fill in {JURISDICTION} or {GEOID}"
    if not matches:
        return f"no jurisdiction's website matches {host}; {ask}"
    return f"{host} is the website of {len(matches)} jurisdictions; {ask}"


def jurisdiction_note(row: dict, resolved: str, jurisdictions: JurisdictionIndex) -> str:
    """What a row's own ids said that the town it resolved to did not, or blank when they agree.

    Information, never a rejection: the row imported, and an id that named nothing was passed
    over rather than trusted. This is the only place a volunteer sees that happen.
    """
    passed_over = []
    typed = clean_cell(row.get(JURISDICTION))
    if typed and typed not in jurisdictions.ocdids:
        passed_over.append(f"{JURISDICTION} {typed} names no jurisdiction")
    geoid = clean_cell(row.get(GEOID))
    if geoid:
        named = jurisdictions.by_geoid.get(normalize_geoid(geoid))
        if not named:
            passed_over.append(f"{GEOID} {geoid} names no jurisdiction")
        elif named != resolved:
            passed_over.append(f"{GEOID} {geoid} names {named}")
    if not passed_over:
        return ""
    return f"matched {resolved}; " + "; ".join(passed_over)


def _row_errors(
    row: dict, line: int, jurisdiction: str, sites: SiteIndex
) -> list[RowError]:
    def error(column: str, message: str) -> RowError:
        return RowError(
            line=line, jurisdiction_ocdid=jurisdiction, column=column, message=message
        )

    errors = [error(column, "required") for column in _REQUIRED if not clean_cell(row.get(column))]
    site_error = _site_error(row, jurisdiction, sites)
    if site_error:
        errors.append(error(JURISDICTION, site_error))
    # The same checks `SubmittedPersonRecord` applies, run here so a bad cell is a rejected row
    # the volunteer sees in the sheet rather than a record that fails further down.
    for column, ok, expected in (
        ("phone", lambda v: normalize_phone_number(v) is not None, "not a phone number"),
        ("email", is_valid_email, "not an email address"),
        ("source_url", is_web_url, "not an http(s) url with a domain"),
    ):
        value = clean_cell(row.get(column))
        if value and not ok(value):
            errors.append(error(column, f"{expected}: {value!r}"))
    return errors


def _import_row(
    row: dict, line: int, jurisdiction: str, sites: SiteIndex, jurisdictions: JurisdictionIndex
) -> ImportRow:
    source_url = clean_cell(row["source_url"])
    return ImportRow(
        line=line,
        jurisdiction_ocdid=jurisdiction,
        status=clean_cell(row.get("status")),
        jurisdiction_note=jurisdiction_note(row, jurisdiction, jurisdictions),
        sighting=Sighting(
            name=clean_cell(row["name"]),
            other_names=_names(row.get("other_names")),
            label=clean_cell(row.get("label")),
            source_url=source_url,
            organization_id=organization_on_site(sites, jurisdiction, source_url),
            email=_optional(row.get("email")),
            phone=_optional(row.get("phone")),
            image=_optional(row.get("image")),
        ),
    )


def _duplicate_errors(rows: list[ImportRow]) -> list[RowError]:
    """One row per person per jurisdiction: `row_key`, which the write-back's notes key on, is
    (jurisdiction, name), and a membership is one open row per (person, organization)."""
    seen: dict[tuple, int] = {}
    errors = []
    for row in rows:
        key = row_key(row.jurisdiction_ocdid, row.sighting.name)
        if key in seen:
            errors.append(
                RowError(
                    line=row.line,
                    jurisdiction_ocdid=row.jurisdiction_ocdid,
                    column="name",
                    message=f"already on line {seen[key]} for this jurisdiction",
                )
            )
        else:
            seen[key] = row.line
    return errors


def row_key(jurisdiction_ocdid: str, name: str) -> tuple[str, str]:
    """A row's identity within one read: `_duplicate_errors` makes it unique. Not the line —
    write-back re-reads the tab, and a row inserted since would shift every line."""
    return (clean_cell(jurisdiction_ocdid), clean_cell(name).lower())


def already_handled(rows: list[ImportRow]) -> bool:
    return all(row.status for row in rows)


def rows_by_jurisdiction(rows: list[ImportRow]) -> dict[str, list[ImportRow]]:
    grouped: dict[str, list[ImportRow]] = {}
    for row in rows:
        grouped.setdefault(row.jurisdiction_ocdid, []).append(row)
    return grouped
