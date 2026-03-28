import asyncio
import csv
import io
import logging
from datetime import date
from typing import Any, Optional
import database.database
import database.people
import database.requests
import services.github.github_api_service as github_service
import shared.utils.id_utils
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from schemas.common import Identity, Role, RouteCategory
from utils.auth_utils import require_route_access

logger = logging.getLogger(__name__)

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

CSV_FIELDNAMES = [
    "request_id",
    "jurisdiction_ocdid",
    "created_at",
    "review_issues",
    "diff_status",
    "changed_fields",
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


def _flatten_official(
    request_id: str,
    jurisdiction_ocdid: str,
    created_at: str | None,
    review_issues: str,
    official: dict,
    diff_status: str,
    changed_fields: list[str],
) -> dict:
    office = official.get("office") or {}
    return {
        "request_id": request_id,
        "jurisdiction_ocdid": jurisdiction_ocdid,
        "created_at": created_at or "",
        "review_issues": review_issues,
        "diff_status": diff_status,
        "changed_fields": " | ".join(changed_fields),
        "id": official.get("id", ""),
        "name": official.get("name", ""),
        "other_names": " | ".join(official.get("other_names") or []),
        "office_name": office.get("name", ""),
        "office_division_ocdid": office.get("division_ocdid", ""),
        "phones": " | ".join(official.get("phones") or []),
        "emails": " | ".join(official.get("emails") or []),
        "urls": " | ".join(official.get("urls") or []),
        "source_urls": " | ".join(official.get("source_urls") or []),
        "start_date": official.get("start_date") or "",
        "end_date": official.get("end_date") or "",
        "updated_at": official.get("updated_at") or "",
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
            official = pr
            changed = []
        elif not pr:
            diff_status = "removed"
            official = existing
            changed = []
        else:
            changed = _changed_field_names(existing, pr)
            diff_status = "changed" if changed else "unchanged"
            official = pr

        if diff_status == "unchanged" and not include_unchanged:
            continue

        rows.append(_flatten_official(
            request["request_id"],
            request["jurisdiction_ocdid"],
            request["created_at"],
            review_issues,
            official,
            diff_status,
            changed,
        ))

    return rows


class CreateRegisterRequest(BaseModel):
    request_id: str
    arguments: dict

class PostResultRequest(BaseModel):
    pull_request_url: Optional[str] = None
    data: Optional[Any] = None


def get_router(api_key_header):
    router = APIRouter()

    @router.post(
            "/register",
            summary="Register a new request",
            description="Register a new request in the system.",
            include_in_schema=False,
        )
    async def register_people_job_endpoint(
        request: CreateRegisterRequest,
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, [Role.MAINTAINERS])),
    ):
        print(
            f"Registering request: {request.request_id} by user {user.provider_user_id} from provider {user.provider}"
        )
        _response = await database.requests.register(
            requested_by_user_id=user.id,
            request_id=request.request_id,
            request_type="people",
            arguments_json=request.arguments,
        )
        return {"request_id": request.request_id, "status": "pending"}

    @router.post(
        "/{request_id}/result",
        include_in_schema=False,
    )
    async def post_job_result_endpoint(
        request_id: str,
        request: PostResultRequest,
        user: Identity = Depends(require_route_access(RouteCategory.SERVICE)),
    ):
        errors = []

        tasks = []
        if request.data:  # Called from within civicpatch project
            tasks.append(("result", database.database.update_job_data(request_id, request.data)))
        if request.pull_request_url:  # Called from open-data repo
            tasks.append(
                (
                    "pull_request",
                    database.database.update_job_pull_request_url(
                        request_id, pull_request_url=request.pull_request_url
                    ),
                )
            )

        if tasks:
            results = await asyncio.gather(
                *[t[1] for t in tasks], return_exceptions=True
            )
            for (label, _), result in zip(tasks, results):
                if isinstance(result, Exception):
                    errors.append(f"Failed to update {label}: {result}")
                elif not result:
                    errors.append(f"Failed to update {label}, job may not exist")

        return {"request_id": request_id, "errors": errors}

    @router.get(
        "/export.csv",
        include_in_schema=False,
    )
    async def export_requests_csv(
        state: str = Query(..., description="Two-letter state code, e.g. 'tx'"),
        from_date: Optional[str] = Query(None),
        to_date: Optional[str] = Query(None),
        include_unchanged: bool = Query(False),
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, [Role.MAINTAINERS])),
    ):
        requests_data = await database.database.get_requests_for_export(state, from_date, to_date)

        uncached = [r for r in requests_data if not r["result_data"]]
        if uncached:
            async def _fetch_result_data(r):
                folder = shared.utils.id_utils.jurisdiction_ocdid_to_folder(r["jurisdiction_ocdid"])
                data = await github_service.get_pull_request_file_yaml(
                    r["request_id"], r["jurisdiction_ocdid"], f"data/{folder}.yml"
                )
                r["result_data"] = data or []

            await asyncio.gather(*[_fetch_result_data(r) for r in uncached])

        unique_ocdids = list({r["jurisdiction_ocdid"] for r in requests_data})
        existing_by_ocdid: dict[str, list] = {}
        if unique_ocdids:
            results = await asyncio.gather(
                *[database.people.get_people_by_jurisdiction_ocdid(ocdid) for ocdid in unique_ocdids]
            )
            existing_by_ocdid = dict(zip(unique_ocdids, results))

        def _generate():
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

        filename = f"requests_export_{state}_{date.today().isoformat()}.csv"
        return StreamingResponse(
            _generate(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    return router
