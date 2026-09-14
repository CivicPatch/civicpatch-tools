"""Census TIGER shapefile downloads for map generation.

No persistent cache — each call downloads and discards. Workers are stateless containers,
and this pipeline runs manually and infrequently, so the ~94MB/run cost isn't worth a cache
invalidation surface (see the map pipeline migration plan, decision 4).
"""

import logging
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

import geopandas
import requests

logger = logging.getLogger(__name__)

_STATE_SHP_URL = "https://www2.census.gov/geo/tiger/TIGER2025/STATE/tl_2025_us_state.zip"
_COUNTY_SHP_URL = "https://www2.census.gov/geo/tiger/TIGER2025/COUNTY/tl_2025_us_county.zip"


def _place_shp_url(fips: str) -> str:
    return f"https://www2.census.gov/geo/tiger/TIGER2025/PLACE/tl_2025_{fips}_place.zip"


def _cousub_shp_url(fips: str) -> str:
    return f"https://www2.census.gov/geo/tiger/TIGER2025/COUSUB/tl_2025_{fips}_cousub.zip"


def _download_and_extract(url: str, dest_dir: Path) -> Path:
    """Download a TIGER shapefile ZIP and extract it. Returns the .shp path."""
    logger.info("Downloading TIGER shapefile: %s", url)
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    zip_path = dest_dir / "data.zip"
    zip_path.write_bytes(response.content)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest_dir)
    shp_files = list(dest_dir.glob("*.shp"))
    if not shp_files:
        raise ValueError(f"No shapefile found in {url}")
    return shp_files[0]


def _fetch_shapefile(url: str) -> geopandas.GeoDataFrame:
    with TemporaryDirectory() as tmp:
        return geopandas.read_file(_download_and_extract(url, Path(tmp)))


def _filter_by_state(gdf: geopandas.GeoDataFrame, fips: str) -> geopandas.GeoDataFrame:
    return geopandas.GeoDataFrame(gdf[gdf["STATEFP"] == fips].copy())


def fetch_national_states(fips: str) -> geopandas.GeoDataFrame:
    """One state's boundary, filtered from the national TIGER state shapefile."""
    return _filter_by_state(_fetch_shapefile(_STATE_SHP_URL), fips)


def fetch_all_states() -> geopandas.GeoDataFrame:
    """Every state's boundary — for the national overview, not per-state generation."""
    return _fetch_shapefile(_STATE_SHP_URL)


def fetch_national_counties(fips: str) -> geopandas.GeoDataFrame:
    """One state's counties, filtered from the national TIGER county shapefile."""
    return _filter_by_state(_fetch_shapefile(_COUNTY_SHP_URL), fips)


def fetch_places(fips: str) -> geopandas.GeoDataFrame:
    """Incorporated places (cities, towns) for one state — pulled per-state, not national."""
    return _fetch_shapefile(_place_shp_url(fips))


def fetch_county_subdivisions(fips: str) -> geopandas.GeoDataFrame:
    """Minor civil divisions (townships etc.) for one state — pulled per-state, not national."""
    return _fetch_shapefile(_cousub_shp_url(fips))
