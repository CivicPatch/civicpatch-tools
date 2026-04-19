import httpx


async def resolve_redirect(url: str) -> str:
    """Follow redirects and return the final URL. Falls back to the original on error."""
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
            response = await client.head(url)
            return str(response.url)
    except Exception:
        return url
