import os
import yaml
from services.open_router.llm import run_prompt as run_together_prompt

# Provider names match OpenRouter's provider_name field from the endpoints API.
# Excluded: SambaNova (no response_format), Novita (no response_format)
PROVIDER_COMPARISON = [
    "open_router:DeepInfra",    # $0.21/$0.79, fp4,  100% uptime
    "open_router:Chutes",       # $0.27/$1.00, fp8,  99.6% uptime
    "open_router:SiliconFlow",  # $0.27/$1.00, fp8,  97.3% uptime
    "open_router:AtlasCloud",   # $0.30/$0.95, fp8,  100% uptime
    "open_router:WandB",        # $0.55/$1.65, fp8,  100% uptime
    "open_router:Fireworks",    # $0.56/$1.68,       99.3% uptime
    "open_router:Google",       # $0.60/$1.70,       99.5% uptime
    "open_router:Together",     # $0.60/$1.70,       84.4% uptime
]


def make_provider_client(param, make_prompt_fn):
    provider = param.split(":", 1)[1]
    return {
        "name": f"open_router-{provider}",
        "run_prompt": run_together_prompt,
        "make_prompt": make_prompt_fn,
        "extra_kwargs": {"model_type": "STANDARD", "provider_order": [provider], "allow_fallbacks": False},
    }


def write_comparison_report(evals_dir, comparison):
    os.makedirs(evals_dir, exist_ok=True)
    comparison_path = os.path.join(evals_dir, "comparison.yml")
    with open(comparison_path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"providers": comparison}, f, sort_keys=False)
    print(f"Saved comparison report to {comparison_path}")
