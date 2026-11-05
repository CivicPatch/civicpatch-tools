"""Each law publisher's way from a link into its code to the law a search wants. A handler answers
a page that is not its publisher's as it came."""

from .ecode360 import Fetch
from . import ecode360, municode
from ..schemas import FetchedPage, LawTarget

HANDLERS = (ecode360.resolved, municode.resolved)


async def resolved(page: FetchedPage, target: LawTarget, fetch: Fetch) -> FetchedPage:
    for handler in HANDLERS:
        page = await handler(page, target, fetch)
    return page
