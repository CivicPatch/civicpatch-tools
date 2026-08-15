import os
import yaml
from services.open_router.llm import run_prompt as run_together_prompt

# Providers must support `structured_outputs`, NOT merely `response_format` — run_prompt
# sends a json_schema with strict=True. `response_format` alone only means json_object.
# Get that wrong and OpenRouter filters every endpoint out, and since we send
# allow_fallbacks=False the request fails as:
#     404 {"error":{"message":"No endpoints found for deepseek/deepseek-v4-flash"}}
# which reads like a bad model id rather than an unsatisfiable provider constraint.
#
# That is exactly how SiliconFlow ($0.13/$0.28, cheapest of the ones considered) was picked
# and then failed: it advertises response_format but structured_outputs=False.
#
# Only 13 of the 19 v4-flash endpoints qualify. Catalogue read 2026-08-14; re-check with:
#   curl -s https://openrouter.ai/api/v1/models/deepseek/deepseek-v4-flash/endpoints
#
# Parasail was dropped 2026-08-14: it repeatedly hit the repetition loop, once burning
# 734s on a single call before failing JSON validation, and never completed a run.
# DigitalOcean replaces it — cheapest qualifying endpoint, untested so far.
PROVIDER_COMPARISON = [
    "open_router:DigitalOcean",  # $0.07/$0.17 — cheapest qualifying, uptime_1d 99.1%
    "open_router:DeepInfra",     # $0.09/$0.18 — uptime_1d 99.6%
    "open_router:AtlasCloud",    # $0.14/$0.28 — uptime_1d 99.7%
]


# Pinned so a re-run measures the prompt, not the sampler. Two runs of the identical
# prompt against identical fixtures drifted by up to 0.500 (image), 0.154 (url) and 0.133
# (end_date) at the production temperature of 0.2 — larger than any effect a prompt change
# is likely to have. Production stays at 0.2; see the note in llm.py for why the two differ.
#
# This narrows the variance, it does not remove it: v4-flash is MoE behind dynamic
# batching, so expert routing still shifts between runs. Re-measure drift rather than
# assuming these are now reproducible.
EVAL_TEMPERATURE = 0.0
EVAL_SEED = 20260815


def make_provider_client(param, make_prompt_fn):
    provider = param.split(":", 1)[1]
    return {
        "name": f"open_router-{provider}",
        "run_prompt": run_together_prompt,
        "make_prompt": make_prompt_fn,
        "extra_kwargs": {
            "model_type": "STANDARD",
            "provider_order": [provider],
            "allow_fallbacks": True,
            "temperature": EVAL_TEMPERATURE,
            "seed": EVAL_SEED,
        },
    }


def write_comparison_report(evals_dir, comparison, failures):
    """`failures` is written even when empty so an all-failed run explains itself:
    `providers: {}` alone reads as "no data" rather than "every provider blew up"."""
    os.makedirs(evals_dir, exist_ok=True)
    comparison_path = os.path.join(evals_dir, "comparison.yml")
    with open(comparison_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            {"providers": comparison, "failures": failures}, f, sort_keys=False
        )
    print(f"Saved comparison report to {comparison_path}")
