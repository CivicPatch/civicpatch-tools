"""Where things live inside the zip a people-collector run ships.

The layout is the pipeline's, not ours. These globs are the contract between the two, so they
are spelled here once and nowhere else — reading them inline would let the pipeline's
vocabulary spread through the ingest code.
"""

import json
import os
from typing import NamedTuple

import lib.files as file_utils

ROSTER_PATTERN = "data/*/local/*.yml"
CONTEXT_PATTERN = "data_source/*/local/*/pipeline_run_context.json"
IMAGE_MAP_PATTERN = "data_source/*/local/*/images/image_map.json"
COSTS_PATTERN = "data_source/*/local/*/costs.json"

OUTPUT_PATTERNS = [ROSTER_PATTERN, CONTEXT_PATTERN]
IMAGE_PATTERNS = ["data_source/*/local/*/images/*"]
DEBUG_PATTERNS = [
    "data_source/*/local/*/cache/*",
    COSTS_PATTERN,
    "data_source/*/local/*/pipeline_run.log",
    CONTEXT_PATTERN,
]


class ArtifactDirs(NamedTuple):
    """Three destinations, three fates: `output` is read and published, `images` are uploaded
    and become each person's `cdn_image`, `debug` backs the run log, run context and
    per-source markdown the UI links to."""

    output: str
    debug: str
    images: str


async def unpack(zip_path: str, temp_dir: str) -> ArtifactDirs:
    extracted_dir = os.path.join(temp_dir, "extracted")
    os.makedirs(extracted_dir, exist_ok=True)
    await file_utils.extract_zip(zip_path, extracted_dir)

    dirs = ArtifactDirs(
        output=os.path.join(temp_dir, "output_files"),
        debug=os.path.join(temp_dir, "debug_files"),
        images=os.path.join(temp_dir, "image_files"),
    )
    for destination, patterns in (
        (dirs.output, OUTPUT_PATTERNS),
        (dirs.debug, DEBUG_PATTERNS),
        (dirs.images, IMAGE_PATTERNS),
    ):
        file_utils.copy_files_preserving_hierarchy(
            extracted_dir, destination, patterns=patterns
        )
    return dirs


async def has_expected_output(output_dir: str) -> bool:
    return await file_utils.validate_file_patterns(output_dir, OUTPUT_PATTERNS)


def find_roster_file(output_dir: str) -> str:
    return file_utils.find_file(output_dir, ROSTER_PATTERN)


def read_workflow_context(debug_file_dir: str) -> dict:
    """Absent on a run that failed before writing one, which is not an error here."""
    try:
        path = file_utils.find_file(debug_file_dir, CONTEXT_PATTERN)
        with open(path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def read_image_map(image_file_dir: str) -> dict:
    """Downloaded filename to the url the photo was scraped from.

    Written by the scrape and shipped in the zip beside the images themselves, so cp.org can
    resolve provenance without the pipeline having done it first. Absent on a run that found
    no images, which is not an error.
    """
    try:
        path = file_utils.find_file(image_file_dir, IMAGE_MAP_PATTERN)
    except FileNotFoundError:
        return {}
    with open(path, "r") as f:
        return json.load(f)


def read_costs(debug_file_dir: str) -> dict:
    """Raises if absent, unlike the readers above — the caller reports costs on a best-effort
    basis and already handles the failure."""
    path = file_utils.find_file(debug_file_dir, COSTS_PATTERN)
    with open(path, "r") as f:
        return json.load(f)
