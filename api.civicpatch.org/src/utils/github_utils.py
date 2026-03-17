from urllib.parse import urlparse


def pull_request_url_to_number(url: str) -> str | None:
    path = urlparse(url).path.rstrip("/")
    parts = path.split("/")
    if len(parts) >= 2 and parts[-2] == "pull":
        return parts[-1]
    return None
