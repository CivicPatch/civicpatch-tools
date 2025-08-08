import json
import utils.path_utils as path_utils

def get_municipalities_to_scrape(state, num_to_scrape, geoids_to_ignore=None):
    """
    Returns a list of GEOIDs for municipalities to scrape based on the state and number specified.
    """
    file_path = path_utils.get_municipalities_file_path(state)
    
    with open(file_path, 'r') as file:
        data = json.load(file)
    
    municipalities = [
        municipality for municipality in data['municipalities']
        if len(municipality.get('meta_sources', [])) < 3  # Use .get() with a default empty list
        and municipality.get('website')  # Ensure 'website' exists and is not None
        and (geoids_to_ignore is None or municipality['geoid'] not in geoids_to_ignore)
    ]
    
    geoids = [municipality['geoid'] for municipality in municipalities]
    return geoids[:num_to_scrape]