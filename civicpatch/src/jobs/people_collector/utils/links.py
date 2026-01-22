from typing import List
from jobs.people_collector.schemas import Link, LinkStatus

def get_next_link_with_status(links: List[Link], status: LinkStatus) -> Link | None:
    for link in links:
        if link.status == status.value:
            return link
    return None

def get_link_status_by_url(links: List[Link], url: str) -> LinkStatus | None:
    for link in links:
        if link.url == url:
            return LinkStatus(link.status)
    return None

def get_links_with_status(links: List[Link], statuses: List[LinkStatus]) -> List[Link]:
    return [link for link in links if link.status in [status.value for status in statuses]]