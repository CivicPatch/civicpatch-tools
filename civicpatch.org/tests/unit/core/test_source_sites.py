"""Pure — which jurisdiction and organization a source page belongs to. No mocks."""

import pytest

from core.source_sites import (
    SiteOwner,
    build_site_index,
    jurisdictions_on_site,
    organization_on_site,
    site_host,
)

_CRESCENT = "ocd-jurisdiction/country:us/state:ca/place:crescent_city/government"
_COUNTY = "ocd-jurisdiction/country:us/state:mi/county:osceola/government"
_TOWNSHIP = "ocd-jurisdiction/country:us/state:mi/county:osceola/township:evart/government"


@pytest.mark.unit
@pytest.mark.parametrize(
    "url",
    [
        "https://www.crescentcity.org/departments/CityCouncil",
        "http://CrescentCity.org",
        "crescentcity.org/council",
    ],
)
def test_a_host_ignores_scheme_case_and_www(url):
    assert site_host(url) == "crescentcity.org"


@pytest.mark.unit
def test_a_page_on_one_jurisdictions_site_finds_it():
    index = build_site_index([SiteOwner(jurisdiction_ocdid=_CRESCENT, url="https://crescentcity.org")])

    assert jurisdictions_on_site(index, "https://www.crescentcity.org/council") == [_CRESCENT]


@pytest.mark.unit
def test_a_shared_site_names_every_jurisdiction_on_it():
    """A county site hosting its townships: the caller must refuse to pick."""
    index = build_site_index(
        [
            SiteOwner(jurisdiction_ocdid=_COUNTY, url="https://osceola-county.org"),
            SiteOwner(jurisdiction_ocdid=_TOWNSHIP, url="https://osceola-county.org/evart"),
        ]
    )

    assert jurisdictions_on_site(index, "https://osceola-county.org/x") == [_COUNTY, _TOWNSHIP]


@pytest.mark.unit
def test_an_organizations_site_names_its_jurisdiction_and_itself():
    index = build_site_index(
        [
            SiteOwner(jurisdiction_ocdid=_CRESCENT, url="https://crescentcity.org"),
            SiteOwner(
                jurisdiction_ocdid=_CRESCENT, organization_id="org-schools", url="https://ccusd.org"
            ),
        ]
    )

    assert jurisdictions_on_site(index, "https://ccusd.org/board") == [_CRESCENT]
    assert organization_on_site(index, _CRESCENT, "https://ccusd.org/board") == "org-schools"
    # The jurisdiction's own site is no body's: the default organization applies.
    assert organization_on_site(index, _CRESCENT, "https://crescentcity.org/council") is None


@pytest.mark.unit
def test_two_bodies_on_one_site_leave_the_default():
    index = build_site_index(
        [
            SiteOwner(jurisdiction_ocdid=_CRESCENT, organization_id="org-a", url="https://city.gov"),
            SiteOwner(jurisdiction_ocdid=_CRESCENT, organization_id="org-b", url="https://city.gov"),
        ]
    )

    assert organization_on_site(index, _CRESCENT, "https://city.gov/page") is None
