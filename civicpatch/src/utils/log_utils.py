from utils import id_utils

# TODO: implement
def log_search_engine_call(state, municipality_name, search_engine_name):
    """
    Logs the search engine call details.

    Args:
        state (str): The state of the municipality.
        municipality_name (str): The name of the municipality.
        search_engine_name (str): The name of the search engine used.
    """
    print(f"Search Engine Call: {search_engine_name} for {municipality_name} in {state}")

# TODO: implement
def log_llm_cost(jurisdiction_id: str, llm_name: str, model: str, input_tokens, output_tokens, with_search=False):
    """
    Logs the LLM call details.
    """
    jurisdiction_id_parts = id_utils.parse_jurisdiction_id(jurisdiction_id)
    state = jurisdiction_id_parts.state
    maybe_county_and_place = ""
    if jurisdiction_id_parts.county:
        maybe_county_and_place += f"county:{jurisdiction_id_parts.county}/"
    maybe_county_and_place += f"place:{jurisdiction_id_parts.place}"

    print(f"LLM Call: {llm_name} for {maybe_county_and_place} in {state}, Model: {model}, Input Tokens: {input_tokens}, Output Tokens: {output_tokens}, With Search: {with_search}")