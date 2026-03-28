import asyncio
import database.database
import database.people
import services.github.github_api_service as github_service
import shared.utils.id_utils


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


async def _fill_result_data(r: dict) -> None:
    folder = shared.utils.id_utils.jurisdiction_ocdid_to_folder(r["jurisdiction_ocdid"])
    data = await github_service.get_pull_request_file_yaml(
        r["request_id"], r["jurisdiction_ocdid"], f"data/{folder}.yml"
    )
    r["result_data"] = data or []
