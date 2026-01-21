import os
import instructor
import time
# from openai import OpenAI
from utils.request_utils import with_retry
from utils.log_utils import get_workflow_logger
from utils import cost_utils

MODEL = "openai/gpt-5-mini"
MAX_RETRIES = 5
OPENAI_URL = "https://api.openai.com/v1/responses"

def run_prompt(request_id, jurisdiction_ocdid: str, prompt, response_schema, content=""):
    """
    Run a prompt against OpenAI's API
    """
    logger = get_workflow_logger(jurisdiction_ocdid)
    logger.info(f"Running OpenAI prompt")
    logger.debug(f"Prompt: \n{prompt}")
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

        cost_utils.add_llm_cost(
            logger,
            request_id,
            jurisdiction_ocdid, 
            "openai", 
            MODEL, 
            input_tokens_num, 
            output_tokens_num, 
            with_search=False
        )

        return response

    start_time = time.time()
    result = with_retry(logger, MAX_RETRIES, execute)
    end_time = time.time()
    logger.info(f"openai LLM call took {end_time - start_time:.2f} seconds")
    return result
