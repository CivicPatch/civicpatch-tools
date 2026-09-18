"""Which jurisdiction and organization a source page belongs to, read off the site it is on.

Pure: the caller reads the known sites and builds the index. A host that more than one
jurisdiction uses answers nothing — picking one would file a roster under the wrong town.
"""

from urllib.parse import urlsplit

from pydantic import BaseModel

_WWW = "www."


def site_host(url: str) -> str:
    """`https://www.City.gov/council` → `city.gov`. A url written without a scheme still parses."""
    text = url.strip()
    host = urlsplit(text if "://" in text else f"//{text}").hostname or ""
    return host.removeprefix(_WWW)


class SiteOwner(BaseModel):
    jurisdiction_ocdid: str
    # None for the jurisdiction's own site; set for a site that belongs to one of its bodies.
    organization_id: str | None = None
    url: str


class SiteIndex(BaseModel):
    owners_by_host: dict[str, list[SiteOwner]] = {}


def build_site_index(owners: list[SiteOwner]) -> SiteIndex:
    by_host: dict[str, list[SiteOwner]] = {}
    for owner in owners:
        host = site_host(owner.url)
        if host:
            by_host.setdefault(host, []).append(owner)
    return SiteIndex(owners_by_host=by_host)


def jurisdictions_on_site(index: SiteIndex, source_url: str) -> list[str]:
    """Every jurisdiction whose own site, or one of whose bodies' sites, `source_url` is on."""
    owners = index.owners_by_host.get(site_host(source_url), [])
    return sorted({owner.jurisdiction_ocdid for owner in owners})


def organization_on_site(
    index: SiteIndex, jurisdiction_ocdid: str, source_url: str
) -> str | None:
    """The one body of this jurisdiction whose site `source_url` is on, else None — the default
    organization then applies."""
    owners = index.owners_by_host.get(site_host(source_url), [])
    organization_ids = {
        owner.organization_id
        for owner in owners
        if owner.jurisdiction_ocdid == jurisdiction_ocdid and owner.organization_id
    }
    if len(organization_ids) != 1:
        return None
    return next(iter(organization_ids))
