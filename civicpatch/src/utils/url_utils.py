from urllib.parse import urlparse

def format_url(url: str):
    """
    Formats a URL by ensuring it has the correct scheme and is properly encoded.
    """
    if not url.startswith("http"):
        url = "https://" + url
    return url.strip().rstrip("/").lower()

def format_url_to_folder(url: str):
    """
    Formats a URL to be used as a folder name by replacing special characters with underscores.
    """
    return url.replace("https://", "").replace("http://", "").replace("/", "_").replace(":", "_").replace(".", "_").lower()

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


