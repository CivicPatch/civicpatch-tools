import os
import time
import instructor
import openai
from typing import List, Dict, Any
# from langchain.text_splitter import MarkdownHeaderTextSplitter
from utils.request_utils import with_retry
from utils.log_utils import get_pipeline_logger
from utils import cost_utils

PROMPT_TOKENS=600
OUTPUT_BUFFER=1500

MAX_RETRIES = 5
BASE_URL = "https://api.together.xyz/v1"

MODELS_BY_TYPE = {
    "CHEAP": {
        "model": "meta-llama/Meta-Llama-3-8B-Instruct-Lite",
        "input_cost": 0.10 / 1000000,
        "output_cost": 0.10 / 1000000,
        "token_limit": 8192,
    },
    "STANDARD": { # Used for municipality official extraction
        # MUNICIPALITY_PROMPT TESTS
        # FAILS @ temperature 0.2, top_p 1.0
            # Sometimes returns only 1 instead of 8 offiicials
        # "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
        # "input_cost": 0,
        # "output_cost": 0
        # FAILS
            # Returns missing JSON fields
            # Takes a long time
        # "model": "google/gemma-3n-E4B-it",
        # "input_cost": 0.02 / 1000000,
        # "output_cost": 0.04 / 1000000
        # FAILS
            # token limit exceeded - default test with 3147 input tokens
        #"model": "openai/gpt-oss-20b",
        #"input_cost": 0.05 / 1000000,
        #"output_cost": 0.10 / 1000000
        # FAILS
            # Good result, but Zack Zappone is missing??
            # TODO: figure out chunking, maybe it's being cut off
            # Cannot differentiate between ward and districts
        #"model": "meta-llama/Llama-3.2-3B-Instruct-Turbo",
        #"input_cost": 0.06 / 1000000,
        #"output_cost": 0.06 / 1000000,
        #"token_limit": 4096,  # Actual token limit is 4096, leave buffer for output tokens
        # PASSES with flying colors
        #"model": "meta-llama/Meta-Llama-3-8B-Instruct-Lite",
        #"input_cost": 0.10 / 1000000,
        #"output_cost": 0.10 / 1000000,
        #"token_limit": 8192,
        # FAILS -- need to RETRY!
        #"model": "openai/gpt-oss-120b",
        #"input_cost": 0.15 / 1000000,
        #"output_cost": 0.60 / 1000000,
        #"token_limit": 4096,  # Actual token limit is 4096, leave buffer for output tokensjj
        # FAILS - need to chunk
          # Model limit is 4096 tokens (sent 4312 -- 2264 in messages, 2048 in completion)
        #"model": "marin-community/marin-8b-instruct",
        #"input_cost": 0.18 / 1000000,
        #"output_cost": 0.18 / 1000000,
        #"token_limit": 6500
        # FAILS - does not support response schema (tool use)
        # "model": "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B",
        # "input_cost": 0.18 / 1000000,
        # "output_cost": 0.18 / 1000000
        # PASSES - just need to fix phone number formatting before comparison
        # "model": "arcee_ai/arcee-spotlight",
        # "input_cost": 0.18 / 1000000,
        # "output_cost": 0.18 / 1000000
        # FAILS
            # OK generation, but took too long because response was bad so needed retriee
        # "model": "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
        # "input_cost": 0.18 / 1000000,
        # "output_cost": 0.18 / 1000000
        # FAILS
            # It needed retries 
        # "model": "deepcogito/cogito-v2-preview-llama-109B-MoE",
        # "input_cost": 0.18 / 1000000,
        # "output_cost": 0.59 / 1000000
        # PASSES
            # Flying colors -- as of sept 18 -- no longer available
        # "model": "meta-llama/Llama-3-8b-chat-hf",
        # "input_cost": 0.20 / 1000000,
        # "output_cost": 0.20 / 1000000,
        # "token_limit"
        # ???
        #"model": "meta-llama/Llama-4-Scout-17B-16E-Instruct",
        #"input_cost": 0.18 / 1000000,
        #"output_cost": 0.59 / 100000
        # FAILS
            # Maybe a better prompt would help?
            # Issues with extracting divisions/making up divisions 
        # "model": "mistralai/Mistral-7B-Instruct-v0.1",
        # "input_cost": 0.20 / 1000000,
        # "output_cost": 0.20 / 1000000
        # ???
        # "model": "google/gemma-3n-E4B-it",
        # "input_cost": 0.02 / 1000000,
        # "output_cost": 0.04 / 1000000
        # FAILS
            # Takes too long, more for batch jobs
            # Did not stick around to get result
        # "model": "Qwen/Qwen3-235B-A22B-Instruct-2507-tput",
        # "input_cost": 0.20 / 1000000,
        # "output_cost": 0.60 / 1000000
        # FAILS 
            # Now costs close to google gemini 2.5 flash 
            # Needed too many retries to pass data validition
            # Failed because of timeout
        # "model": "Qwen/Qwen2.5-7B-Instruct-Turbo",
        # "input_cost": 0.30 / 1000000,
        # "output_cost": 0.30 / 1000000
        "model": "mistralai/Mixtral-8x7B-Instruct-v0.1",
        "input_cost": 0.60 / 1000000,
        "output_cost": 0.60 / 1000000
    },
}

def run_prompt(request_id, jurisdiction_id: str, prompt, content="", response_schema=None, model_type="STANDARD"):
    """
    Run a prompt against Together AI's API using OpenAI-compatible interface
    """
    logger = get_pipeline_logger(jurisdiction_id)
    logger.info(f"Running Together AI prompt: {prompt}")
    logger.debug(f"Prompt: \n{prompt}")
    api_key = os.getenv("TOGETHER_AI_TOKEN")
    if not api_key:
        raise ValueError("TOGETHER_AI_TOKEN is not set")

    # Get model configuration
    model_config = MODELS_BY_TYPE.get(model_type, MODELS_BY_TYPE["STANDARD"])
    model = model_config["model"]

    # Set up messages
    messages = [
        {"role": "system", "content": prompt}
    ]
    
    if content:
        messages.append({"role": "user", "content": content})

    # Execute request with retries
    def execute():
        together_client = openai.OpenAI(api_key=api_key, base_url=BASE_URL)
        client = instructor.from_openai(together_client)

        response, completion = client.chat.completions.create_with_completion(
            model=model,
            response_model=response_schema,
            messages=messages,
            temperature=0.2,
            top_p=1.0
        )

        # Log token usage
        usage = completion.usage
        
        cost_utils.add_llm_cost(
            logger,
            request_id,
            jurisdiction_id, 
            "together_ai", 
            model, 
            usage.prompt_tokens, 
            usage.completion_tokens, 
            with_search=False
        )

        return response

    start_time = time.time()
    result = with_retry(logger, MAX_RETRIES, execute)
    end_time = time.time()
    logger.info(f"together_ai LLM call took {end_time - start_time:.2f} seconds")
    return result