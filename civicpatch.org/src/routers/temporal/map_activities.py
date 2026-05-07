import json
import subprocess
import tempfile
from pathlib import Path

import boto3
import httpx
from temporalio import activity

import database.jurisdictions as jurisdictions_db
from environment import get_env_vars

OPEN_DATA_RAW_BASE = "https://raw.githubusercontent.com/CivicPatch/open-data/refs/heads/main"


def _enrich_geojson(geojson: dict, geoid_map: dict[str, dict]) -> dict:
    enriched = []
    for feature in geojson.get("features", []):
        props = feature.get("properties", {})
        geoid = str(props.get("GEOID") or props.get("geoid") or "")
        match = geoid_map.get(geoid)
        if not match:
            continue
        enriched.append({
            "type": "Feature",
            "geometry": feature["geometry"],
            "properties": {
                "jurisdiction_ocdid": match["jurisdiction_ocdid"],
                "name": match["name"],
            },
        })
    return {"type": "FeatureCollection", "features": enriched}


@activity.defn
async def sync_jurisdiction_map_activity(state: str) -> str:
    env = get_env_vars()

    geoid_map = await jurisdictions_db.get_jurisdictions_by_geoid(state)

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.get(f"{OPEN_DATA_RAW_BASE}/data/{state}/.maps/local.geojson")
        resp.raise_for_status()

    enriched = _enrich_geojson(json.loads(resp.text), geoid_map)
    activity.logger.info("state=%s matched_features=%d", state, len(enriched["features"]))

    with tempfile.TemporaryDirectory() as tmp:
        tmp_geojson = Path(tmp) / f"{state}.geojson"
        tmp_pmtiles = Path(tmp) / f"{state}.pmtiles"

        tmp_geojson.write_text(json.dumps(enriched))

        subprocess.run(
            [
                "tippecanoe",
                "-o", str(tmp_pmtiles),
                "--layer", "jurisdictions",
                "--maximum-zoom", "14",
                "--drop-densest-as-needed",
                "--force",
                str(tmp_geojson),
            ],
            check=True,
            capture_output=True,
        )

        s3 = boto3.client(
            "s3",
            endpoint_url=env["STORAGE_ENDPOINT"],
            aws_access_key_id=env["STORAGE_ACCESS_KEY_ID"],
            aws_secret_access_key=env["STORAGE_SECRET_ACCESS_KEY"],
        )
        s3_key = f"maps/{state}.pmtiles"
        s3.upload_file(
            str(tmp_pmtiles),
            "civicpatch",
            s3_key,
            ExtraArgs={"ContentType": "application/octet-stream"},
        )

    return f"{env['FRIENDLY_STORAGE_HOST']}/{s3_key}"
