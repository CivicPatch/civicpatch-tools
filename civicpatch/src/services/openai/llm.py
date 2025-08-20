import os
import json
import instructor
# from openai import OpenAI
from utils.request_utils import with_retry
from utils.log_utils import log_llm_cost
from utils.data_utils import MunicipalityContext

MODEL = "openai/gpt-4.1-mini"
MAX_RETRIES = 5
OPENAI_URL = "https://api.openai.com/v1/responses"

def run_prompt(municipality_context: MunicipalityContext, prompt, response_schema, content=""):
    """
    Run a prompt against OpenAI's API
    """
    api_key = os.getenv("OPENAI_TOKEN")
    if not api_key:
        raise ValueError("OPENAI_TOKEN is not set in environment variables.")

    # Set up messages
    messages = [
        {"role": "system", "content": prompt}
    ]
    
    if content:
        messages.append({"role": "user", "content": content})

    def execute():
        client = instructor.from_provider(model=MODEL, api_key=api_key)
        response, completion = client.chat.completions.create_with_completion(
            response_model=response_schema,
            messages=messages
        )

        usage = completion.usage
        input_tokens_num = usage.prompt_tokens
        output_tokens_num = usage.completion_tokens

        log_llm_cost(municipality_context, "openai", MODEL, input_tokens_num, output_tokens_num, with_search=False)

        return response

    return with_retry(MAX_RETRIES, execute)