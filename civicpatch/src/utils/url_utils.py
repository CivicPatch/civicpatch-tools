def format_url(url: str):
    """
    Formats a URL by ensuring it has the correct scheme and is properly encoded.
    """
    if not url.startswith("http"):
        url = "https://" + url
    return url.strip().lower()

def format_url_to_folder(url: str):
    """
    Formats a URL to be used as a folder name by replacing special characters with underscores.
    """
    return url.replace("https://", "").replace("http://", "").replace("/", "_").replace(":", "_").replace(".", "_").lower()