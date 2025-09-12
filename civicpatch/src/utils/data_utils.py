import os
import utils.path_utils
import json
from schemas import MunicipalityContext

def get_municipality_context(state: str, geoid: str) -> MunicipalityContext:
    """
    Returns the absolute path to the municipalities directory for a given state and GEOID.
    """
    municipalities_path = utils.path_utils.get_municipalities_file_path(state)

    if not os.path.exists(municipalities_path):
        raise FileNotFoundError(f"Municipalities path not found at {municipalities_path}")

    municipality_entry = {}
    
    with open(municipalities_path, "r") as municipalities_file:
        data = json.load(municipalities_file)
        municipalities = data.get("municipalities", {})
        if not municipalities:
            raise ValueError(f"No municipalities found for state {state}")
        
        for municipality in municipalities:
            if municipality.get("geoid") == geoid:
                municipality_entry = municipality
                break

    municipality_context = MunicipalityContext(
        state=state,
        geoid=geoid,
        municipality_entry=municipality_entry,
    )

    return municipality_context


def get_municipality_folder_name(state, geoid):
    """
    Returns the folder name for the municipality based on state and GEOID.
    """
    municipality_context = get_municipality_context(state, geoid)
    municipality_name = municipality_context.municipality_entry.name.replace(" ", "_").lower()

    if len(municipality_context.municipality_entry.counties) > 1:
        # If there are multiple counties, append the geoid to the folder name
        return f"{municipality_name}_{geoid}"
    
    return municipality_name