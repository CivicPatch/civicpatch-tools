import asyncio
import database.database
import database.people
import services.csv_service as csv_service
import services.github.github_api_service as github_service
import shared.utils.id_utils

PEOPLE_CSV_FIELDNAMES = [
    "jurisdiction_ocdid",
    "id",
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

_EMPTY_FIELDS = {f: "" for f in _SIDE_BY_SIDE_FIELDS}


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
        "name": csv_service.sanitize(official.get("name") or ""),
        "other_names": csv_service.sanitize(" | ".join(official.get("other_names") or [])),
        "office_name": csv_service.sanitize(office.get("name") or ""),
        "office_division_ocdid": csv_service.sanitize(office.get("division_ocdid") or ""),
        "phones": csv_service.sanitize(" | ".join(official.get("phones") or [])),
        "emails": csv_service.sanitize(" | ".join(official.get("emails") or [])),
        "urls": csv_service.sanitize(" | ".join(official.get("urls") or [])),
        "source_urls": csv_service.sanitize(" | ".join(official.get("source_urls") or [])),
        "start_date": csv_service.sanitize(official.get("start_date") or ""),
        "end_date": csv_service.sanitize(official.get("end_date") or ""),
        "updated_at": csv_service.sanitize(official.get("updated_at") or ""),
    }


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


def _request_to_rows(request: dict, existing_people: list[dict], include_unchanged: bool) -> list[dict]:
    review_issues = " | ".join((request["review_json"] or {}).get("issues") or [])
    result_data = request["result_data"] or []

    existing_map = {p["id"]: p for p in existing_people if p.get("id")}
    pr_map = {p["id"]: p for p in result_data if p.get("id")}

    rows = []
    for oid in set(existing_map) | set(pr_map):
        existing = existing_map.get(oid)
        pr = pr_map.get(oid)

        if not existing:
            diff_status, changed = "added", []
        elif not pr:
            diff_status, changed = "removed", []
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


def get_export_rows(
    requests_data: list[dict],
    existing_by_ocdid: dict[str, list],
    include_unchanged: bool,
) -> list[dict]:
    rows = []
    for request in requests_data:
        existing = existing_by_ocdid.get(request["jurisdiction_ocdid"], [])
        rows.extend(_request_to_rows(request, existing, include_unchanged))
    return rows


async def fetch_export_data(
    state: str,
    from_date: str | None,
    to_date: str | None,
) -> tuple[list[dict], dict[str, list]]:
    requests_data = await database.database.get_requests_for_export(state, from_date, to_date)

    uncached = [r for r in requests_data if not r["result_data"]]
    if uncached:
        await asyncio.gather(*[_fill_result_data(r) for r in uncached])

    unique_ocdids = list({r["jurisdiction_ocdid"] for r in requests_data})
    existing_by_ocdid: dict[str, list] = {}
    if unique_ocdids:
        results = await asyncio.gather(
            *[database.people.get_people_by_jurisdiction_ocdid(ocdid) for ocdid in unique_ocdids]
        )
        existing_by_ocdid = dict(zip(unique_ocdids, results))

    return requests_data, existing_by_ocdid


async def fetch_people_export_rows(state: str) -> list[dict]:
    people = await database.database.get_people_by_state(state)
    rows = []
    for p in people:
        office = p.get("office") or {}
        rows.append({
            "jurisdiction_ocdid": p.get("jurisdiction_ocdid", ""),
            "id": p.get("id", ""),
            "name": csv_service.sanitize(p.get("name") or ""),
            "other_names": csv_service.sanitize(" | ".join(p.get("other_names") or [])),
            "office_name": csv_service.sanitize(office.get("name") or ""),
            "office_division_ocdid": csv_service.sanitize(office.get("division_ocdid") or ""),
            "phones": csv_service.sanitize(" | ".join(p.get("phones") or [])),
            "emails": csv_service.sanitize(" | ".join(p.get("emails") or [])),
            "urls": csv_service.sanitize(" | ".join(p.get("urls") or [])),
            "source_urls": csv_service.sanitize(" | ".join(p.get("source_urls") or [])),
            "start_date": csv_service.sanitize(p.get("start_date") or ""),
            "end_date": csv_service.sanitize(p.get("end_date") or ""),
            "updated_at": csv_service.sanitize(p.get("updated_at") or ""),
        })
    return rows


async def _fill_result_data(r: dict) -> None:
    folder = shared.utils.id_utils.jurisdiction_ocdid_to_folder(r["jurisdiction_ocdid"])
    data = await github_service.get_pull_request_file_yaml(
        r["request_id"], r["jurisdiction_ocdid"], f"data/{folder}.yml"
    )
    r["result_data"] = data or []
