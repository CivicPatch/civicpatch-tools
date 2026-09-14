"""Builds and uploads one state's map tiles: TIGER geometry, enrichment against
civicpatch's own jurisdiction records, the county-overlay parent_ocdids write-back,
tippecanoe, and the R2 upload. See .scratch/2026-09-11-plan-map-pipeline-migration.md.
"""

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory

import geopandas
import pandas

import environment
import lib.buckets as buckets
import lib.storage as storage
import lib.tiger as tiger
import lib.tippecanoe as tippecanoe
from core.images import promoted_url
from core.map_county_overlay import local_county_ocdids
from core.map_enrichment import (
    GeoidEntry,
    enrich_county_feature,
    enrich_local_feature,
    enrich_state_feature,
    feature_collection,
)
from database.jurisdictions import (
    get_all_states_geoid_lookup,
    get_geoid_lookup,
    get_state_fips,
    set_parent_ocdids,
)


async def generate_and_upload_state_pmtiles(state: str) -> str:
    """Build {state}.pmtiles (states/counties/local layers) and upload it to R2, returning
    the CDN URL. Also recomputes and writes parent_ocdids for the state's local
    jurisdictions — the county overlay needs the same polygon geometry this fetches
    anyway, and it's the only thing that produces parent_ocdids at all.
    """
    fips = await get_state_fips(state)
    if fips is None:
        raise ValueError(f"No active state jurisdiction found for '{state}'")
    lookup = await get_geoid_lookup(state)

    url, parent_ocdids_by_ocdid = await asyncio.to_thread(
        _build_and_upload_pmtiles, state, fips, lookup
    )
    await set_parent_ocdids(parent_ocdids_by_ocdid)
    return url


def _build_and_upload_pmtiles(
    state: str, fips: str, lookup: dict[str, GeoidEntry]
) -> tuple[str, dict[str, list[str]]]:
    """Everything that doesn't touch the DB: TIGER fetch, enrichment, tippecanoe, upload.
    Runs off the event loop via asyncio.to_thread — network fetches, geopandas, and the
    tippecanoe subprocess are all blocking calls.
    """
    state_gdf, county_gdf, local_gdf = _fetch_state_geometry(fips)

    county_ocdids_by_geoid = local_county_ocdids(local_gdf, county_gdf, lookup)
    parent_ocdids_by_ocdid = _parent_ocdids_by_ocdid(county_ocdids_by_geoid, lookup, fips)

    state_features = [enrich_state_feature(f, lookup) for f in _to_features(state_gdf)]
    county_features = [enrich_county_feature(f, lookup) for f in _to_features(county_gdf)]
    local_features = _enrich_local_features(local_gdf, county_ocdids_by_geoid, lookup)

    pmtiles_bytes = _build_pmtiles(
        [
            ("states", state_features, 0),
            ("counties", county_features, 5),
            ("local", local_features, 8),
        ],
        f"{state}.pmtiles",
        label=state,
    )
    url = _upload(f"maps/{state}.pmtiles", pmtiles_bytes)
    return url, parent_ocdids_by_ocdid


def _fetch_state_geometry(
    fips: str,
) -> tuple[geopandas.GeoDataFrame, geopandas.GeoDataFrame, geopandas.GeoDataFrame]:
    # Four independent TIGER downloads — run concurrently rather than one after another,
    # since none depends on another's result.
    with ThreadPoolExecutor(max_workers=4) as executor:
        state_future = executor.submit(tiger.fetch_national_states, fips)
        county_future = executor.submit(tiger.fetch_national_counties, fips)
        # Places and county subdivisions, unconditionally — no need to know upfront which
        # one a given state treats as its real local-government layer (open-data's
        # per-state config for that). Whichever doesn't match a real jurisdiction row in
        # `lookup` gets silently dropped by enrich_local_feature below.
        places_future = executor.submit(tiger.fetch_places, fips)
        cousubs_future = executor.submit(tiger.fetch_county_subdivisions, fips)

        state_gdf = state_future.result()
        county_gdf = county_future.result()
        local_gdf = geopandas.GeoDataFrame(
            pandas.concat(
                [places_future.result(), cousubs_future.result()], ignore_index=True
            )
        )
    return state_gdf, county_gdf, local_gdf


def _to_features(gdf: geopandas.GeoDataFrame) -> list[dict]:
    return json.loads(gdf.to_json())["features"]


def _enrich_local_features(
    local_gdf: geopandas.GeoDataFrame,
    county_ocdids_by_geoid: dict[str, list[str]],
    lookup: dict[str, GeoidEntry],
) -> list[dict]:
    features = []
    for feature in _to_features(local_gdf):
        geoid = str(feature["properties"].get("GEOID") or "")
        feature["properties"]["county_ocdids"] = county_ocdids_by_geoid.get(geoid, [])
        enriched = enrich_local_feature(feature, lookup)
        if enriched is not None:
            features.append(enriched)
    return features


def _parent_ocdids_by_ocdid(
    county_ocdids_by_geoid: dict[str, list[str]],
    lookup: dict[str, GeoidEntry],
    fips: str,
) -> dict[str, list[str]]:
    state_entry = lookup.get(fips)
    state_ocdid = state_entry.ocdid if state_entry else ""
    return {
        entry.ocdid: [*county_ocdids, state_ocdid]
        for geoid, county_ocdids in county_ocdids_by_geoid.items()
        if (entry := lookup.get(geoid)) is not None
    }


def _build_pmtiles(
    layers: list[tuple[str, list[dict], int]], output_name: str, label: str
) -> bytes:
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        output_path = tmp_path / output_name
        tippecanoe_layers = []
        for name, features, min_zoom in layers:
            path = tmp_path / f"{name}.geojson"
            path.write_text(json.dumps(feature_collection(features)))
            tippecanoe_layers.append((name, path, min_zoom))
        tippecanoe.run_tippecanoe(tippecanoe_layers, output_path, label=label)
        return output_path.read_bytes()


def _upload(key: str, body: bytes) -> str:
    storage.upload_bytes_to_storage(buckets.CDN, key, body, "application/octet-stream")
    friendly_storage_host = environment.get_env_vars()["FRIENDLY_STORAGE_HOST"]
    return promoted_url(friendly_storage_host, key)


async def generate_and_upload_national_overview() -> str:
    """Rebuild states.pmtiles — the coverage picker `browse-map.ts` loads unconditionally,
    showing which states have data before one is clicked. Chained onto the end of every
    per-state run (see plan decision 5) rather than a separate manual trigger: it only
    needs the state layer, so it's cheap, and re-running it after every onboarding keeps
    the picker from silently omitting a newly-added state.
    """
    lookup = await get_all_states_geoid_lookup()
    return await asyncio.to_thread(_build_and_upload_national_overview, lookup)


def _build_and_upload_national_overview(lookup: dict[str, GeoidEntry]) -> str:
    all_states_gdf = tiger.fetch_all_states()
    active_fips = list(lookup.keys())
    active_gdf = geopandas.GeoDataFrame(
        all_states_gdf[all_states_gdf["STATEFP"].isin(active_fips)].copy()
    )
    features = [enrich_state_feature(f, lookup) for f in _to_features(active_gdf)]

    body = _build_pmtiles([("states", features, 0)], "states.pmtiles", label="national")
    return _upload("maps/states.pmtiles", body)
