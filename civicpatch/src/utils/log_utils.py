from schemas import MunicipalityContext

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
def log_llm_cost(municipality_context: MunicipalityContext, llm_name: str, model: str, input_tokens, output_tokens, with_search=False):
    """
    Logs the LLM call details.

    Args:
        municipality_context (MunicipalityContext): The context of the municipality.
    """
    state = municipality_context.state
    municipality_name = municipality_context.municipality_entry.name
    print(f"LLM Call: {llm_name} for {municipality_name} in {state}, Model: {model}, Input Tokens: {input_tokens}, Output Tokens: {output_tokens}, With Search: {with_search}")