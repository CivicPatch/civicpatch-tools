import steps.step_01_collecting.search as search

def collect(state, geoid):
    """
    Collects data for a given state and GEOID.
    """

    try:
        candidate_urls = search.get_candidate_urls(state, geoid)

        if not candidate_urls:
            print(f"No candidate URLs found for state {state} and GEOID {geoid}.")
            
            # TODO: should fail at this step so we can surface the error
            return

        for url in candidate_urls:
            print(f"Scraping URL: {url}")
            content = scrape(url)
            print(f"Content scraped from {url}: {content[:100]}...")  # Print first 100 characters

    except Exception as e:
        print(f"Error during collection: {e}")