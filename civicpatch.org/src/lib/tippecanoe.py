"""Thin wrapper around the tippecanoe CLI (vector-tile builder)."""

import json
import logging
import subprocess
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

# A wedged tippecanoe (bad input geometry, disk contention) would otherwise block on
# `for line in process.stderr` forever — Temporal's activity timeout can't interrupt a
# blocking call already running in a worker thread, so the kill has to happen here.
# Comfortably under both call sites' activity timeouts (15 min state / 10 min national).
_TIPPECANOE_TIMEOUT_SECONDS = 300


def run_tippecanoe(layers: list[tuple[str, Path, int]], output_path: Path, label: str = "") -> None:
    """Build one .pmtiles file from named GeoJSON layers.

    layers: (layer_name, geojson_path, min_zoom) tuples, one per source-layer in the
    output — e.g. states/counties/local at different minzooms in the same file.
    """
    cmd = [
        "tippecanoe",
        "-o", str(output_path),
        "--maximum-zoom", "14",
        "--no-feature-limit",
        "--simplification", "10",
        "--force",
    ]
    for layer_name, geojson_path, min_zoom in layers:
        layer_spec = json.dumps({"file": str(geojson_path), "layer": layer_name, "minzoom": min_zoom})
        cmd.extend(["-L", layer_spec])

    prefix = f"[{label}] " if label else ""
    process = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True)
    assert process.stderr is not None  # guaranteed by stderr=subprocess.PIPE above

    timed_out = False

    def _kill_on_timeout() -> None:
        nonlocal timed_out
        timed_out = True
        process.kill()

    timer = threading.Timer(_TIPPECANOE_TIMEOUT_SECONDS, _kill_on_timeout)
    timer.start()
    try:
        for line in process.stderr:
            logger.info("%s%s", prefix, line.rstrip())
        process.wait()
    finally:
        timer.cancel()

    if timed_out:
        raise TimeoutError(f"{prefix}tippecanoe exceeded {_TIPPECANOE_TIMEOUT_SECONDS}s and was killed")
    if process.returncode != 0:
        raise subprocess.CalledProcessError(process.returncode, cmd)
