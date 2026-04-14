import os
import yaml
from services.open_router.llm import run_prompt as run_together_prompt

# Providers confirmed working for deepseek/deepseek-v3.2 via curl test 2026-04-14
# Excluded: DeepSeek (404), DeepInfra (429/BYOK required), AkashML (429/BYOK required),
#           Novita (no response_format), Together/WandB (model not available)
PROVIDER_COMPARISON = [
    "open_router:AtlasCloud",   # $0.26/$0.38
    "open_router:SiliconFlow",  # $0.27/$0.42
    "open_router:Google",       # $0.56/$1.68
]


def make_provider_client(param, make_prompt_fn):
    provider = param.split(":", 1)[1]
    return {
        "name": f"open_router-{provider}",
        "run_prompt": run_together_prompt,
        "make_prompt": make_prompt_fn,
        "extra_kwargs": {"model_type": "STANDARD", "provider_order": [provider], "allow_fallbacks": True},
    }


def write_comparison_report(evals_dir, comparison):
    os.makedirs(evals_dir, exist_ok=True)
    comparison_path = os.path.join(evals_dir, "comparison.yml")
    with open(comparison_path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"providers": comparison}, f, sort_keys=False)
    print(f"Saved comparison report to {comparison_path}")
