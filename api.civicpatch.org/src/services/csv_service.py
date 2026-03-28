import csv
import io
from typing import Generator

_DIFF_FIELDS = [
    "name",
    "office.name",
    "office.division_ocdid",
    "phones",
    "emails",
    "urls",
    "start_date",
    "end_date",
]

_SIDE_BY_SIDE_FIELDS = [
    "name",
    "other_names",
    "office_name",
    "office_division_ocdid",
    "phones",
    "emails",
    "urls",
    "source_urls",
    "start_date",
    "end_date",
    "updated_at",
]

CSV_FIELDNAMES = [
    "request_id",
    "jurisdiction_ocdid",
    "created_at",
    "review_issues",
    "diff_status",
    "changed_fields",
    "id",
    *[f"existing_{f}" for f in _SIDE_BY_SIDE_FIELDS],
    *[f"proposed_{f}" for f in _SIDE_BY_SIDE_FIELDS],
]

# Characters that spreadsheet applications (Excel, Sheets) interpret as formula prefixes
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _sanitize(val: str) -> str:
    """Prevent CSV formula injection by prefixing dangerous values with a single quote."""
    if val and val[0] in _FORMULA_PREFIXES:
        return "'" + val
    return val


def _get_field(official: dict, key: str) -> str:
    if key == "office.name":
        val = (official.get("office") or {}).get("name", "")
    elif key == "office.division_ocdid":
        val = (official.get("office") or {}).get("division_ocdid", "")
    else:
        val = official.get(key, "")
    if isinstance(val, list):
        return " | ".join(str(v) for v in val)
    return str(val or "")


def _normalize(val: str) -> str:
    return val.lower().strip()


def _changed_field_names(existing: dict, pr: dict) -> list[str]:
    return [k for k in _DIFF_FIELDS if _normalize(_get_field(existing, k)) != _normalize(_get_field(pr, k))]


def _extract_fields(official: dict) -> dict:
    office = official.get("office") or {}
    return {
        "name": _sanitize(official.get("name") or ""),
        "other_names": _sanitize(" | ".join(official.get("other_names") or [])),
        "office_name": _sanitize(office.get("name") or ""),
        "office_division_ocdid": _sanitize(office.get("division_ocdid") or ""),
        "phones": _sanitize(" | ".join(official.get("phones") or [])),
        "emails": _sanitize(" | ".join(official.get("emails") or [])),
        "urls": _sanitize(" | ".join(official.get("urls") or [])),
        "source_urls": _sanitize(" | ".join(official.get("source_urls") or [])),
        "start_date": _sanitize(official.get("start_date") or ""),
        "end_date": _sanitize(official.get("end_date") or ""),
        "updated_at": _sanitize(official.get("updated_at") or ""),
    }


_EMPTY_FIELDS = {f: "" for f in _SIDE_BY_SIDE_FIELDS}


def _flatten_official(
    request_id: str,
    jurisdiction_ocdid: str,
    created_at: str | None,
    review_issues: str,
    existing: dict | None,
    proposed: dict | None,
    diff_status: str,
    changed_fields: list[str],
) -> dict:
    existing_fields = _extract_fields(existing) if existing else _EMPTY_FIELDS
    proposed_fields = _extract_fields(proposed) if proposed else _EMPTY_FIELDS
    official_id = (proposed or existing or {}).get("id", "")
    return {
        "request_id": request_id,
        "jurisdiction_ocdid": jurisdiction_ocdid,
        "created_at": created_at or "",
        "review_issues": review_issues,
        "diff_status": diff_status,
        "changed_fields": " | ".join(changed_fields),
        "id": official_id,
        **{f"existing_{k}": v for k, v in existing_fields.items()},
        **{f"proposed_{k}": v for k, v in proposed_fields.items()},
    }


def _request_to_rows(
    request: dict,
    existing_people: list[dict],
    include_unchanged: bool,
) -> list[dict]:
    review_issues = " | ".join((request["review_json"] or {}).get("issues") or [])
    result_data = request["result_data"] or []

    existing_map = {p["id"]: p for p in existing_people if p.get("id")}
    pr_map = {p["id"]: p for p in result_data if p.get("id")}
    all_ids = set(existing_map) | set(pr_map)

    rows = []
    for oid in all_ids:
        existing = existing_map.get(oid)
        pr = pr_map.get(oid)

        if not existing:
            diff_status = "added"
            changed = []
        elif not pr:
            diff_status = "removed"
            changed = []
        else:
            changed = _changed_field_names(existing, pr)
            diff_status = "changed" if changed else "unchanged"

        if diff_status == "unchanged" and not include_unchanged:
            continue

        rows.append(_flatten_official(
            request["request_id"],
            request["jurisdiction_ocdid"],
            request["created_at"],
            review_issues,
            existing,
            pr,
            diff_status,
            changed,
        ))

    return rows


def generate_requests_csv(
    requests_data: list[dict],
    existing_by_ocdid: dict[str, list],
    include_unchanged: bool,
) -> Generator[str, None, None]:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_FIELDNAMES, lineterminator="\n")
    writer.writeheader()
    yield buf.getvalue()

    for request in requests_data:
        existing = existing_by_ocdid.get(request["jurisdiction_ocdid"], [])
        for row in _request_to_rows(request, existing, include_unchanged):
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=CSV_FIELDNAMES, lineterminator="\n")
            writer.writerow(row)
            yield buf.getvalue()
