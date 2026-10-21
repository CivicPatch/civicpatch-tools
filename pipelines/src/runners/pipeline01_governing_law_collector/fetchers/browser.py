from ..schemas import FetchedPage


async def fetch(url: str) -> FetchedPage:
    """For script-rendered pages. Not built until a page needs it: Vermont's do not."""
    raise NotImplementedError(f"no browser fetcher yet, and {url} was nearly empty by plain GET")
