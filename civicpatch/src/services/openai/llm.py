import os
import instructor
import time
# from openai import OpenAI
from utils.request_utils import with_retry
from utils.log_utils import log_llm_cost, get_pipeline_logger

MODEL = "openai/gpt-4.1-mini"
MAX_RETRIES = 5
OPENAI_URL = "https://api.openai.com/v1/responses"

def run_prompt(jurisdiction_id: str, prompt, response_schema, content=""):
    """
    Run a prompt against OpenAI's API
    """
    logger = get_pipeline_logger(jurisdiction_id)
    logger.debug(f"Running OpenAI prompt: {prompt}")
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

        log_llm_cost(jurisdiction_id, "openai", MODEL, input_tokens_num, output_tokens_num, with_search=False)

        return response

    start_time = time.time()
    result = with_retry(logger, MAX_RETRIES, execute)
    end_time = time.time()
    logger.info(f"openai LLM call took {end_time - start_time:.2f} seconds")
    return result
