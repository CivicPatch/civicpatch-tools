import json
from functools import lru_cache
from pathlib import Path

_MANIFEST = Path("src/frontend/build/.vite/manifest.json")
_DEV_SERVER = "http://localhost:5173"


@lru_cache(maxsize=None)
def _load_manifest() -> dict:
    with open(_MANIFEST) as f:
        return json.load(f)


def vite_asset(path: str, production: bool) -> str:
    if not production:
        return f"{_DEV_SERVER}/{path}"
    entry = _load_manifest()[path]
    return f"/frontend/build/{entry['file']}"


def vite_css(path: str, production: bool) -> list[str]:
    if not production:
        return []
    manifest = _load_manifest()
    return _collect_css(path, manifest, set())


def _collect_css(key: str, manifest: dict, seen: set) -> list[str]:
    if key in seen:
        return []
    seen.add(key)
    entry = manifest.get(key, {})
    css = [f"/frontend/build/{f}" for f in entry.get("css", [])]
    for imported_key in entry.get("imports", []):
        css.extend(_collect_css(imported_key, manifest, seen))
    return css
