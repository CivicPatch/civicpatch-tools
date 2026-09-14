import geopandas

from core.map_enrichment import GeoidEntry

# Floating-point guard only, NOT a policy cutoff. TIGER's place and county layers are
# topologically integrated, so an overlap is either a real shared area or exact zero —
# there are no digitisation slivers to filter out. Every county a place genuinely reaches
# is recorded, however small; ordering by descending share is what identifies the primary
# county.
_MIN_COUNTY_AREA_SHARE = 1e-9


def local_county_ocdids(
    local_gdf: geopandas.GeoDataFrame,
    counties_gdf: geopandas.GeoDataFrame,
    county_lookup: dict[str, GeoidEntry],
) -> dict[str, list[str]]:
    """geoid -> county_ocdids for every local feature that materially overlaps at least
    one county, ordered by descending area share (the county a place mostly sits in leads
    the list — Bothell WA spans King and Snohomish, King first).

    Overlays the full polygons rather than joining centroids: a centroid lies in exactly
    one county by construction, so a centroid join can never see a place that straddles a
    county line.
    """
    local_gdf = geopandas.GeoDataFrame(local_gdf.reset_index(drop=True))
    local_projected = local_gdf.to_crs("EPSG:5070")
    counties_projected = counties_gdf.to_crs("EPSG:5070")

    pieces = local_projected[["geometry"]].reset_index(names="local_index").overlay(  # pyright: ignore[reportCallIssue]
        counties_projected[["GEOID", "geometry"]],
        how="intersection",
        keep_geom_type=True,
    )
    pieces["share"] = (
        pieces.geometry.area
        / local_projected.geometry.area.reindex(pieces["local_index"]).to_numpy()
    )
    pieces = pieces[pieces["share"] >= _MIN_COUNTY_AREA_SHARE]
    pieces = pieces.sort_values(["local_index", "share"], ascending=[True, False])
    county_geoid_map: dict[int, list[str]] = (
        pieces.groupby("local_index")["GEOID"].apply(list).to_dict()
    )

    result: dict[str, list[str]] = {}
    for i, row in local_gdf.iterrows():
        # local_gdf was reset to a plain RangeIndex above, so `i` is always an int at
        # runtime — iterrows()'s Hashable type is just the general pandas index type.
        row_index: int = i  # pyright: ignore[reportAssignmentType]
        geoid = str(row.get("GEOID") or row.get("geoid") or "")
        if not geoid:
            continue
        county_ocdids = [
            entry.ocdid
            for county_geoid in county_geoid_map.get(row_index, [])
            if (entry := county_lookup.get(str(county_geoid)))
        ]
        if county_ocdids:
            result[geoid] = county_ocdids

    return result
