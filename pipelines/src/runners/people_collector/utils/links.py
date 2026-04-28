from typing import List
from runners.people_collector.schemas import Link, LinkStatus, LinkFrontier


def get_next_link_with_status(frontier: LinkFrontier, status: LinkStatus) -> Link | None:
    return frontier.next_with_status(status)


def get_link_status_by_url(frontier: LinkFrontier, url: str) -> LinkStatus | None:
    return frontier.status_of(url)


def get_links_with_status(frontier: LinkFrontier, statuses: List[LinkStatus]) -> List[Link]:
    return frontier.all_with_status(statuses)


def add_links(frontier: LinkFrontier, urls: List[str]) -> LinkFrontier:
    return frontier.add(urls)
