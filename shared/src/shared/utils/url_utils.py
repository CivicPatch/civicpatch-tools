import re
from urllib.parse import urlparse, urlunparse

# Any scheme, not just http. `startswith("http")` was both case-sensitive — so "HTTP://x"
# got a second scheme prepended and became unreachable — and too loose, since a host
# beginning "http" ("httpbin.org") looked like it already carried one and got none.
_SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://")


def is_valid_url(url: str):
    """
    Validates a URL by checking its scheme and netloc.
    """
    try:
        result = urlparse(url)
        return all([result.scheme in ("http", "https"), result.netloc])
    except Exception:
        return False


def format_url(url: str):
    """
    Formats a URL into a canonical form for storage:
    - Lowercases scheme and host
    - Prepends https:// if no scheme present
    - Preserves trailing slash as-is
    """
    url = url.strip()
    if url.startswith("//"):
        url = "https:" + url
    elif not _SCHEME.match(url):
        url = "https://" + url

    parsed = urlparse(url)
    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
    )
    return urlunparse(normalized)


def canonical_url(url: str) -> str:
    """
    Returns the canonical form of a URL for use as a dict key.
    Lowercases everything, strips www, strips the fragment, strips trailing slash,
    normalizes to https.
    Two URLs are equivalent iff their canonical forms are equal.

    The fragment is dropped because it addresses a position inside a document, not a
    different document: `/council#top` and `/council` are one page to fetch and one page
    to store.

    Trailing slash is stripped from the path rather than the whole string, so that it still
    goes when something follows it — `/council/#top` and `/council/?x=1` kept theirs while
    `/council/` lost it, which put the same page under two keys.
    """
    parsed = urlparse(format_url(url))
    normalized = parsed._replace(
        scheme="https",
        netloc=parsed.netloc.removeprefix("www."),
        path=parsed.path.rstrip("/"),
        fragment="",
    )
    return urlunparse(normalized).lower()


def same_url(url1: str, url2: str) -> bool:
    """
    Check if two URLs are the same after normalization.
    Treats http/https and www/non-www as equivalent.
    """
    return canonical_url(url1) == canonical_url(url2)


def url_in_text(url: str, text: str) -> bool:
    """
    Check if a URL appears in text, tolerating www./non-www. variants.
    """
    url_lower = url.lower()
    text_lower = text.lower()
    if url_lower in text_lower:
        return True
    www_variant = (
        url_lower.replace("://", "://www.", 1)
        if "://www." not in url_lower
        else url_lower.replace("://www.", "://", 1)
    )
    return www_variant in text_lower


def extract_domain(url: str):
    """
    Extracts the domain from a URL.
    """

    try:
        parsed_url = urlparse(url)
        return parsed_url.netloc.lower()
    except Exception:
        return None


def same_domain(domain: str, url: str) -> bool:
    """
    Check if the given URL belongs to the same domain as the provided domain.
    Args:
        domain (str): The base domain. https://seattle.gov
        url (str): The URL to check. https://www.seattle.gov/city-council
    Returns:
        bool: True if the URL belongs to the same domain, False otherwise.
    """
    base_host = extract_domain(domain)
    link_host = extract_domain(url)

    if not base_host or not link_host:
        return False

    core_base_host = base_host.removeprefix("www.")
    core_link_host = link_host.removeprefix("www.")

    return core_base_host == core_link_host


def format_url_to_folder(url: str):
    """
    Formats a URL to be used as a folder name by replacing special characters with underscores.
    """
    return (
        url.replace("https://", "")
        .replace("http://", "")
        .replace("/", "_")
        .replace(":", "_")
        .replace(".", "_")
        .lower()
    )


def get_path(url: str) -> str:
    return urlparse(url).path
