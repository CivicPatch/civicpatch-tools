def format_url():
    """
    Formats a URL by ensuring it has the correct scheme and is properly encoded.
    """
    if not search_query.startswith("http"):
        search_query = "https://" + search_query
    return search_query.strip().lower()