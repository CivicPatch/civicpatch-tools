def log_search_engine_call(state, municipality_name, search_engine_name):
    """
    Logs the search engine call details.

    Args:
        state (str): The state of the municipality.
        municipality_name (str): The name of the municipality.
        search_engine_name (str): The name of the search engine used.
    """
    print(f"Search Engine Call: {search_engine_name} for {municipality_name} in {state}")