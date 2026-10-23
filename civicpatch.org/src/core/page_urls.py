"""Absolute links to civicpatch pages, for API responses an agent passes on to a person."""

ROSTER_COMPARISON_PAGE_PREFIX = "/roster-comparisons"


def jurisdiction_page_url(instance_url: str, jurisdiction_ocdid: str) -> str:
    """A jurisdiction's public page: its ocdid is the path (see `frontend.jurisdiction_page`)."""
    return f"{instance_url.rstrip('/')}/{jurisdiction_ocdid}"


def roster_comparison_page_url(instance_url: str, run_id: str) -> str:
    return f"{instance_url.rstrip('/')}{ROSTER_COMPARISON_PAGE_PREFIX}/{run_id}"
