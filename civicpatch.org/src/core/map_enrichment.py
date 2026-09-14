from typing import NamedTuple


class GeoidEntry(NamedTuple):
    ocdid: str
    name: str


def enrich_state_feature(feature: dict, lookup: dict[str, GeoidEntry]) -> dict:
    props = feature["properties"]
    entry = lookup.get(str(props["GEOID"]))
    return {
        "type": "Feature",
        "geometry": feature["geometry"],
        "properties": {
            "jurisdiction_ocdid": entry.ocdid if entry else "",
            "geoid": props["GEOID"],
            "name": props["NAME"],
            "code": props["STUSPS"].lower(),
        },
    }


def enrich_county_feature(feature: dict, lookup: dict[str, GeoidEntry]) -> dict:
    props = feature["properties"]
    entry = lookup.get(str(props["GEOID"]))
    return {
        "type": "Feature",
        "geometry": feature["geometry"],
        "properties": {
            "jurisdiction_ocdid": entry.ocdid if entry else "",
            "geoid": props["GEOID"],
            "name": props["NAMELSAD"],
        },
    }


def enrich_local_feature(feature: dict, lookup: dict[str, GeoidEntry]) -> dict | None:
    props = feature.get("properties", {})
    geoid = str(props.get("GEOID") or props.get("geoid") or "")
    entry = lookup.get(geoid)
    if not entry:
        return None
    return {
        "type": "Feature",
        "geometry": feature["geometry"],
        "properties": {
            "jurisdiction_ocdid": entry.ocdid,
            "geoid": geoid,
            "name": entry.name,
            "county_ocdids": props.get("county_ocdids", []),
        },
    }


def feature_collection(features: list[dict]) -> dict:
    return {"type": "FeatureCollection", "features": features}
