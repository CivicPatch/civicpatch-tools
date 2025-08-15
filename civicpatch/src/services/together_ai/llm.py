import os
import json
import instructor
import openai
from utils.request_utils import with_retry
from utils.log_utils import log_llm_cost
from utils.data_utils import MunicipalityContext

MAX_RETRIES = 5
BASE_URL = "https://api.together.xyz/v1"

MODELS_BY_TYPE = {
    "CHEAP": "together/instructor-medium",
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
        #"model": "meta-llama/Llama-3.2-3B-Instruct-Turbo",
        #"input_cost": 0.06 / 1000000,
        #"output_cost": 0.06 / 1000000
        # PASSES with flying colors
        #"model": "meta-llama/Meta-Llama-3-8B-Instruct-Lite",
        #"input_cost": 0.10 / 1000000,
        #"output_cost": 0.10 / 1000000
        # FAILS -- need to RETRY!
        # "model": "openai/gpt-oss-120b",
        # "input_cost": 0.15 / 1000000,
        # "output_cost": 0.60 / 1000000
        # FAILS - need to chunk
          # Model limit is 4096 tokens (sent 4312 -- 2264 in messages, 2048 in completion)
        # "model": "marin-community/marin-8b-instruct",
        # "input_cost": 0.18 / 1000000,
        # "output_cost": 0.18 / 1000000
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
            # Flying colors
        # "model": "meta-llama/Llama-3-8b-chat-hf",
        # "input_cost": 0.20 / 1000000,
        # "output_cost": 0.20 / 1000000
        # FAILS
            # Maybe a better prompt would help?
            # Issues with extracting divisions/making up divisions 
        # "model": "mistralai/Mistral-7B-Instruct-v0.1",
        # "input_cost": 0.20 / 1000000,
        # "output_cost": 0.20 / 1000000
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
    },
}

def run_prompt(municipality_context: MunicipalityContext, prompt, response_schema=None, model_type="STANDARD"):
    api_key = os.getenv("TOGETHER_AI_TOKEN")
    model = MODELS_BY_TYPE.get(model_type, MODELS_BY_TYPE["STANDARD"])["model"]

    if not api_key:
        raise ValueError("TOGETHER_AI_TOKEN is not set in environment variables.")

    def execute():
        together_client = openai.OpenAI(api_key=api_key, base_url=BASE_URL)
        client = instructor.from_openai(together_client)
        response, completion = client.chat.completions.create_with_completion(
            model=model,
            response_model=response_schema,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            top_p=1.0
        )

        usage = completion.usage
        input_tokens_num = usage.prompt_tokens
        output_tokens_num = usage.completion_tokens

        log_llm_cost(municipality_context, "together_ai", model, input_tokens_num, output_tokens_num, with_search=False)

        return response.model_dump()

    return with_retry(MAX_RETRIES, execute)