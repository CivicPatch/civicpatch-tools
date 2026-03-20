from urllib.parse import urlparse, urlunparse

def format_url(url: str):
    """
    Formats a URL into a canonical form for storage and comparison:
    - Lowercases scheme, host, and path
    - Strips www. prefix from host
    - Strips trailing slash
    """
    url = url.strip().rstrip("/")
    if not url.startswith("http"):
        url = "https://" + url

    parsed = urlparse(url)
    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower().removeprefix("www."),
        path=parsed.path.lower(),
    )
    return urlunparse(normalized)

# For the purposes of comparing
def normalize_url(url: str):
    return format_url(url).lower()

def same_url(url1: str, url2: str) -> bool:
    """
    Check if two URLs are the same after normalization.
    """
    return normalize_url(url1) == normalize_url(url2)

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
    return url.replace("https://", "").replace("http://", "").replace("/", "_").replace(":", "_").replace(".", "_").lower()

def is_valid_url(url: str) -> bool:
    """
    Validates a URL by checking its scheme and netloc.
    """
    try:
        result = urlparse(url)
        return all([result.scheme in ("http", "https"), result.netloc])
    except Exception:
        return False
    
def get_path(url: str) -> str:
    return urlparse(url).path