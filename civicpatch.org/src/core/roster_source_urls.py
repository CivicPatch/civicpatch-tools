from pydantic import BaseModel

from shared.schemas import Person

# A page two or more people were read from is a roster; one with a single person is their bio.
ROSTER_PAGE_MINIMUM_PEOPLE = 2


class OrganizationSourceUrls(BaseModel):
    organization_id: str
    urls: list[str]


def roster_source_urls_by_organization(people: list[Person], organization_ids: list[str]) -> list[OrganizationSourceUrls]:
    """An organization's roster pages, else (a one-person office) all its pages. A shared page is
    listed once, under the organization with the most people on it."""
    people_by_url = _people_by_url_and_organization(people)
    order = _organization_order(people_by_url, organization_ids)
    pages_by_organization: dict[str, list[str]] = {}
    for url, people_by_organization in people_by_url.items():
        owner = _most_people(people_by_organization, order)
        pages_by_organization.setdefault(owner, []).append(url)

    groups = []
    for organization_id in order:
        urls = _by_most_people(pages_by_organization.get(organization_id, []), people_by_url)
        groups.append(OrganizationSourceUrls(organization_id=organization_id, urls=_roster_pages_else_all(urls, people_by_url)))
    return groups


def _people_by_url_and_organization(people: list[Person]) -> dict[str, dict[str, set[str]]]:
    people_by_url: dict[str, dict[str, set[str]]] = {}
    for person in people:
        for membership in person.memberships:
            for url in membership.source_urls:
                by_organization = people_by_url.setdefault(url, {})
                by_organization.setdefault(membership.organization_id, set()).add(person.id)
    return people_by_url


def _organization_order(people_by_url: dict[str, dict[str, set[str]]], organization_ids: list[str]) -> list[str]:
    order = list(organization_ids)
    for people_by_organization in people_by_url.values():
        for organization_id in people_by_organization:
            if organization_id not in order:
                order.append(organization_id)
    return order


def _most_people(people_by_organization: dict[str, set[str]], order: list[str]) -> str:
    return min(
        people_by_organization,
        key=lambda organization_id: (-len(people_by_organization[organization_id]), order.index(organization_id)),
    )


def _people_on(url: str, people_by_url: dict[str, dict[str, set[str]]]) -> int:
    return len(set().union(*people_by_url[url].values()))


def _by_most_people(urls: list[str], people_by_url: dict[str, dict[str, set[str]]]) -> list[str]:
    return sorted(urls, key=lambda url: -_people_on(url, people_by_url))


def _roster_pages_else_all(urls: list[str], people_by_url: dict[str, dict[str, set[str]]]) -> list[str]:
    roster_pages = [url for url in urls if _people_on(url, people_by_url) >= ROSTER_PAGE_MINIMUM_PEOPLE]
    return roster_pages or urls
