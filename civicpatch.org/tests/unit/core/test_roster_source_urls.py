import pytest

from shared.schemas import Membership, Person
from core.roster_source_urls import OrganizationSourceUrls, roster_source_urls_by_organization

pytestmark = pytest.mark.unit

COUNCIL = "council"
MAYOR = "office-of-the-mayor"
ROSTER = "https://city.gov/council"
ELECTED = "https://city.gov/elected-officials"


def _person(person_id: str, organization_id: str, source_urls: list[str]) -> Person:
    return Person(
        id=person_id,
        name=person_id,
        jurisdiction_ocdid="ocd-jurisdiction/country:us/state:wa/place:example/government",
        memberships=[
            Membership(
                post_id=f"{person_id}-post",
                organization_id=organization_id,
                source_urls=source_urls,
                role_id="council-member",
                division_ocdid="ocd-division/country:us/state:wa/place:example",
                role_label="Council Member",
            )
        ],
    )


def test_a_roster_page_drops_the_bios():
    people = [
        _person("ana", COUNCIL, [ROSTER, "https://city.gov/ana"]),
        _person("ben", COUNCIL, [ROSTER, "https://city.gov/ben"]),
    ]

    assert roster_source_urls_by_organization(people, [COUNCIL]) == [OrganizationSourceUrls(organization_id=COUNCIL, urls=[ROSTER])]


def test_a_one_person_organization_keeps_its_page():
    people = [_person("mo", MAYOR, ["https://city.gov/mayor"])]

    assert roster_source_urls_by_organization(people, [MAYOR]) == [
        OrganizationSourceUrls(organization_id=MAYOR, urls=["https://city.gov/mayor"])
    ]


def test_everyone_on_their_own_bio_keeps_every_bio():
    people = [
        _person("ana", COUNCIL, ["https://city.gov/ana"]),
        _person("ben", COUNCIL, ["https://city.gov/ben"]),
    ]

    assert roster_source_urls_by_organization(people, [COUNCIL])[0].urls == ["https://city.gov/ana", "https://city.gov/ben"]


def test_one_person_on_a_page_twice_counts_once():
    mayor_and_member = _person("mo", COUNCIL, [ROSTER, "https://city.gov/mo"])
    mayor_and_member.memberships.append(mayor_and_member.memberships[0].model_copy())

    assert roster_source_urls_by_organization([mayor_and_member], [COUNCIL])[0].urls == [ROSTER, "https://city.gov/mo"]


def test_people_count_across_organizations():
    people = [
        _person("ana", COUNCIL, [ELECTED, "https://city.gov/ana"]),
        _person("mo", MAYOR, [ELECTED, "https://city.gov/mayor"]),
    ]

    assert roster_source_urls_by_organization(people, [COUNCIL, MAYOR]) == [
        OrganizationSourceUrls(organization_id=COUNCIL, urls=[ELECTED]),
        OrganizationSourceUrls(organization_id=MAYOR, urls=["https://city.gov/mayor"]),
    ]


def test_a_shared_page_goes_to_the_organization_with_most_people_on_it():
    people = [
        _person("ana", COUNCIL, [ELECTED]),
        _person("ben", COUNCIL, [ELECTED]),
        _person("mo", MAYOR, [ELECTED]),
    ]

    assert roster_source_urls_by_organization(people, [MAYOR, COUNCIL]) == [
        OrganizationSourceUrls(organization_id=MAYOR, urls=[]),
        OrganizationSourceUrls(organization_id=COUNCIL, urls=[ELECTED]),
    ]


def test_roster_pages_come_most_people_first():
    people = [
        _person("ana", COUNCIL, ["https://city.gov/committee", ROSTER]),
        _person("ben", COUNCIL, ["https://city.gov/committee", ROSTER]),
        _person("cy", COUNCIL, [ROSTER]),
    ]

    assert roster_source_urls_by_organization(people, [COUNCIL])[0].urls == [ROSTER, "https://city.gov/committee"]


def test_an_organization_not_listed_comes_last():
    people = [_person("mo", MAYOR, ["https://city.gov/mayor"])]

    assert [group.organization_id for group in roster_source_urls_by_organization(people, [COUNCIL])] == [COUNCIL, MAYOR]

