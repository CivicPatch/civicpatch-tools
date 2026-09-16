import hashlib
import os
import re
import pathlib
from datetime import datetime, timezone

import yaml
from services.open_router.llm import MODELS_BY_TYPE
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
# DeepInfra dropped 2026-08-15. Measured across 9 officials runs it misses 125 values to
# DigitalOcean's 63 and AtlasCloud's 6, and extracts *zero* of the 12 start_dates and 12
# end_dates in the corpus — a capability gap, not variance, reproducing identically every
# run. It is out of production routing (llm.py) for the same reason, so comparing against it
# only bought a permanently red gate and a third of the run cost.
# Model id -> providers to compare it on. To trial a model, add an entry and run the eval with
# EVAL_MODEL=<model id>; production keeps routing to MODELS_BY_TYPE["STANDARD"].
PROVIDERS_BY_MODEL = {
    "deepseek/deepseek-v4-flash": [
        "open_router:DigitalOcean",   # $0.10/$0.20, no seed — prices read 2026-09-16
        "open_router:AtlasCloud",     # $0.14/$0.28, seed, fp4
        "open_router:Alibaba",        # $0.13/$0.27, seed, fp8 — added 2026-09-16
        "open_router:NextBit",        # $0.15/$0.35, seed, fp8 — added 2026-09-16
    ],
    "deepseek/deepseek-v4.1-flash": [
        "open_router:Morph",      # $0.18/$0.72, seed, fp8 — catalogue read 2026-09-16
        "open_router:DeepInfra",  # $0.20/$0.60, seed, fp8
        "open_router:Makora",     # $0.30/$1.20, seed
        "open_router:Wafer",      # $0.30/$1.20, seed
        "open_router:Parasail",   # $0.30/$1.20, seed, fp8
    ],
}
EVAL_MODEL = os.environ.get("EVAL_MODEL", MODELS_BY_TYPE["STANDARD"]["model"])
PROVIDER_COMPARISON = PROVIDERS_BY_MODEL[EVAL_MODEL]


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
            "model": EVAL_MODEL,
            "provider_order": [provider],
            "temperature": EVAL_TEMPERATURE,
            "seed": EVAL_SEED,
        },
    }


def _prune_provider_reports(evals_dir: str, providers) -> None:
    """Delete reports for providers this eval no longer runs.

    A dropped provider's report otherwise sits in the directory forever and the dashboard
    renders it as a live column — DeepInfra was dropped from both the comparison and
    production routing on 2026-08-15 and still showed up as a third provider. Same orphan
    problem as the prompt archive.

    A provider that failed this run still counts as participating: erasing its last good
    numbers because one run errored would lose the only record of what it used to score.
    """
    keep = set(providers)
    if not keep:
        return
    for path in pathlib.Path(evals_dir).glob("*-eval-report.yml"):
        if path.name.removesuffix("-eval-report.yml") not in keep:
            path.unlink()


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
    _prune_provider_reports(evals_dir, set(comparison) | set(failures))


_LABEL = re.compile(r"^[ \t]*[A-Z][A-Za-z][A-Za-z /]{1,40}:[ \t]*$")


def _dangling_labels(prompt: str) -> list[str]:
    """Labels with no value and nothing on the line after — an un-substituted placeholder.

    A heading that introduces a list ("Only extract officials from:") also has an empty
    colon, so the following line is what separates the two: a heading is followed by its
    content, a blanked interpolation by nothing.

    This catches half the failure mode. An *optional* block built as
    `f"...{x}" if x else ""` vanishes entirely when x is falsy, and a missing line is
    indistinguishable from one that legitimately does not apply — that is why the convention
    is to archive with a marker (`<page url, per case>`) rather than a real or empty value.
    """
    lines = prompt.splitlines()
    return [
        line.strip()
        for i, line in enumerate(lines)
        if _LABEL.match(line) and not (lines[i + 1].strip() if i + 1 < len(lines) else "")
    ]


def record_run(evals_dir: str, prompt: str) -> dict:
    """Stamp a report with when it ran and which prompt text produced it.

    The prompt is written once to `_prompts/<sha>.txt` and referenced by hash rather than
    inlined into every provider's report — the officials prompt alone is ~110 lines, and
    three copies per run would bury the numbers. Hashing also makes the directory a history
    of prompt versions: a score that moved between runs is attributable to a prompt change
    or not, which is the whole reason for recording it.
    """
    blank = _dangling_labels(prompt)
    if blank:
        raise ValueError(
            "Refusing to archive a prompt with un-substituted placeholders: "
            + ", ".join(repr(b) for b in blank)
            + ". Pass a marker such as '<page url, per case>' rather than an empty value — "
            "the archive is the record of what produced these numbers."
        )

    directory = pathlib.Path(evals_dir) / "_prompts"
    directory.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]
    path = directory / f"{digest}.txt"
    if not path.exists():
        path.write_text(prompt, encoding="utf-8")
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "prompt_sha256": digest,
        "prompt_file": str(path.relative_to(evals_dir)),
    }


HISTORY_DEPTH = 5


def _delete_files_not_named(directory: pathlib.Path, pattern: str, keep: set[str]) -> None:
    for path in directory.glob(pattern):
        if path.name not in keep:
            path.unlink()


def _prune_prompt_archive(evals_dir: str, runs: list) -> None:
    """An empty history means nothing recorded yet, so it must not delete the current prompt."""
    if not runs:
        return
    keep = {f"{run.get('prompt_sha256')}.txt" for run in runs}
    _delete_files_not_named(pathlib.Path(evals_dir) / "_prompts", "*.txt", keep)


def _lineage(run: dict) -> tuple:
    return (run.get("model"), run.get("provider"))


def _keep_recent(runs: list[dict], entry: dict, depth: int) -> list[dict]:
    """Per (model, provider): keyed on provider alone, a new model's runs evict the retired one's."""
    key = _lineage(entry)
    others = [r for r in runs if _lineage(r) != key]
    mine = [r for r in runs if _lineage(r) == key] + [entry]
    return sorted(others + mine[-depth:], key=lambda r: (r.get("provider") or "", r.get("timestamp") or ""))


DISPOSITIONS = ("correct", "missing", "spurious", "wrong")


def _dispositions(accuracy: dict) -> dict:
    """f1 alone can't tell a model that started hallucinating from one that started missing."""
    return {
        field: {name: counts[name] for name in DISPOSITIONS}
        for field, counts in sorted(accuracy.items())
    }


def _mismatches_file(timestamp: str, provider: str) -> str:
    stamp = datetime.fromisoformat(timestamp).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"_runs/{stamp}-{provider}.yml"


def _write_mismatches(evals_dir: str, entry: dict, mismatches: dict) -> str:
    relative = _mismatches_file(entry["timestamp"], entry["provider"])
    path = pathlib.Path(evals_dir) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"mismatches": mismatches}, sort_keys=True), encoding="utf-8")
    return relative


def _prune_run_archive(evals_dir: str, runs: list) -> None:
    if not runs:
        return
    keep = {pathlib.Path(run["mismatches_file"]).name for run in runs if run.get("mismatches_file")}
    _delete_files_not_named(pathlib.Path(evals_dir) / "_runs", "*.yml", keep)


def record_history(
    evals_dir: str,
    provider: str,
    run: dict,
    scores: dict,
    cost: dict,
    cases: dict | None = None,
    *,
    accuracy: dict,
    mismatches: dict | None,
) -> None:
    """Append this run to `history.yml`, keeping the last HISTORY_DEPTH per (model, provider).

    A single run cannot tell you whether a prompt edit helped. Measured 2026-08-15, two
    identical runs of the identical prompt drifted by up to 0.267 (end_date) and 0.154
    (url) — larger than most effects worth detecting. Keeping a short history lets a score
    be read against its own spread, and grouping by `prompt_sha256` turns "before and after"
    into a comparison of two samples rather than two numbers.

    `cases` is a per-case score, kept so a run can be diffed against the previous one. An
    aggregate that falls 0.03 says nothing about whether one case collapsed or five drifted
    slightly, and those call for opposite responses.

    Truncated rather than unbounded: the point is the recent trend, and an ever-growing YAML
    committed on every run is its own problem.

    `mismatches` is None for an eval that doesn't record them; `{}` is a run that had none.
    """
    path = pathlib.Path(evals_dir) / "history.yml"
    existing = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}) if path.exists() else {}
    entry = {
        "timestamp": run.get("timestamp"),
        "provider": provider,
        "model": cost.get("model"),
        "prompt_sha256": run.get("prompt_sha256"),
        "cost_usd": cost.get("total_cost_usd"),
        "elapsed_seconds": cost.get("elapsed_seconds"),
        "scores": {k: v for k, v in sorted(scores.items()) if v is not None},
        "cases": dict(sorted((cases or {}).items())),
        "dispositions": _dispositions(accuracy),
    }
    if mismatches is not None:
        entry["mismatches_file"] = _write_mismatches(evals_dir, entry, mismatches)
    runs = _keep_recent(existing.get("runs") or [], entry, HISTORY_DEPTH)
    path.write_text(yaml.safe_dump({"runs": runs}, sort_keys=False), encoding="utf-8")
    _prune_run_archive(evals_dir, runs)
    _prune_prompt_archive(evals_dir, runs)
