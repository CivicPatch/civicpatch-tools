"""Gate dev tasks on setup and on the LLM keys evals need. Standard library only: it runs before setup has.

Keys come from the environment (CI, or ../pipelines.env loaded by mise), else from Infisical at run time,
never written to disk. In a terminal, check offers to save missing keys to ../pipelines.env. Values are
never printed.

    python3 scripts/dev_env.py require-setup     stop (or offer setup) when mise run setup hasn't run here
    python3 scripts/dev_env.py check             report where the keys come from (mise run setup calls this)
    python3 scripts/dev_env.py run -- <cmd...>   run <cmd> with the keys, or stop before it if any is missing
"""
import getpass
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIRED_KEYS = ("OPEN_ROUTER_TOKEN", "GOOGLE_GEMINI_TOKEN")
# Where each key is created. Each person uses their own account's key.
KEY_LINKS = {
    "OPEN_ROUTER_TOKEN": "https://openrouter.ai/settings/keys",
    "GOOGLE_GEMINI_TOKEN": "https://aistudio.google.com/apikey",
}
PIPELINES_ENV_FILE = ROOT.parent / "pipelines.env"
# Which Infisical: set both in your own mise config (~/.config/mise/config.toml [env]), never in this repo.
INFISICAL_ENV_KEYS = ("INFISICAL_PROJECT_ID", "INFISICAL_DOMAIN")
INFISICAL_ENV = "dev"
INFISICAL_PATH = "/apps/pipelines"
FROM_INFISICAL = "CP_SECRETS_FROM_INFISICAL"
SETUP_COMMAND = ("mise", "run", "setup")
COMMAND_REQUIRE_SETUP = "require-setup"
COMMAND_CHECK = "check"
COMMAND_RUN = "run"
COMMAND_HAS_KEYS = "has-keys"
USAGE_EXIT = 2


# Terminal output: one look per kind of line. Color only on a terminal, and never with NO_COLOR set.
COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
BOLD, GREEN, YELLOW, DIM, RESET = ("\033[1m", "\033[32m", "\033[33m", "\033[2m", "\033[0m") if COLOR else ("",) * 5


def heading(text: str) -> None:
    print(f"\n{BOLD}▸ {text}{RESET}", flush=True)


def action(number: int, text: str) -> None:
    print(f"  {BOLD}{number}.{RESET} {text}", flush=True)


def ok(text: str) -> None:
    print(f"  {GREEN}✓{RESET} {text}", flush=True)


def warn(text: str) -> None:
    print(f"  {YELLOW}!{RESET} {text}", flush=True)


def note(text: str) -> None:
    print(f"  {DIM}{text}{RESET}", flush=True)


def merge_env_file(existing: str, values: dict[str, str]) -> str:
    kept = [line for line in existing.splitlines() if line.split("=", 1)[0].strip() not in values]
    return "\n".join([*kept, *(f"{key}={value}" for key, value in values.items())]) + "\n"


def missing_keys(env: dict[str, str]) -> list[str]:
    return [key for key in REQUIRED_KEYS if not env.get(key)]


def how_to_fix(missing: list[str]) -> str:
    return (
        f"Missing: {' '.join(missing)}\n"
        "mise run setup walks you through it, or do one or both:\n"
        "  - copy pipelines.env.example to ../pipelines.env (outside the repo, gitignored) and fill it in;\n"
        "  - use Infisical: set INFISICAL_DOMAIN and INFISICAL_PROJECT_ID in your own mise config, then\n"
        f"    infisical login; the keys are read from {INFISICAL_ENV} {INFISICAL_PATH} at run time, never written to disk."
    )


def infisical_command(env: dict[str, str], inner: list[str]) -> list[str] | None:
    project_id, domain = (env.get(key, "") for key in INFISICAL_ENV_KEYS)
    if not (project_id and domain):
        return None
    return ["infisical", "run", "--silent", f"--projectId={project_id}", f"--domain={domain}",
            f"--env={INFISICAL_ENV}", f"--path={INFISICAL_PATH}", "--", *inner]


def setup_done() -> bool:
    hook = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--path-format=absolute", "--git-path", "hooks/pre-commit"],
                          capture_output=True, text=True).stdout.strip()
    return (ROOT / ".venv").is_dir() and bool(hook) and os.access(hook, os.X_OK)


def require_setup() -> None:
    if setup_done():
        return
    print("Setup hasn't run in this checkout: mise run setup", file=sys.stderr)
    if not sys.stdin.isatty() or input("Run it now? [Y/n] ").strip().lower() == "n":
        sys.exit(1)
    subprocess.run(SETUP_COMMAND, cwd=ROOT, check=True)


def with_infisical(env: dict[str, str], inner: list[str]) -> subprocess.CompletedProcess | None:
    command = infisical_command(env, inner)
    if command is None:
        return None
    try:
        return subprocess.run(command, env={**env, FROM_INFISICAL: "1"})
    except FileNotFoundError:
        return None


def ask_for_keys(missing: list[str]) -> dict[str, str]:
    heading("LLM keys for evals")
    note("Paste each one (hidden). Enter skips.")
    values = {}
    for key in missing:
        note(f"Get one: {KEY_LINKS[key]}")
        if value := getpass.getpass(f"  {key}: ").strip():
            values[key] = value
    return values


def save_env_file(path: Path, values: dict[str, str]) -> None:
    existing = path.read_text() if path.exists() else ""
    path.write_text(merge_env_file(existing, values))
    path.chmod(0o600)


def check() -> int:
    env = dict(os.environ)
    missing = missing_keys(env)
    if not missing:
        ok("LLM keys: set")
        return 0
    probe = with_infisical(env, [sys.executable, __file__, COMMAND_HAS_KEYS])
    if probe is not None and probe.returncode == 0:
        ok(f"LLM keys: from Infisical {INFISICAL_ENV} {INFISICAL_PATH}")
        return 0
    if sys.stdin.isatty() and (saved := ask_for_keys(missing)):
        save_env_file(PIPELINES_ENV_FILE, saved)
        missing = [key for key in missing if key not in saved]
        ok(f"Saved to {PIPELINES_ENV_FILE}")
    if not missing:
        return 0
    print(how_to_fix(missing), file=sys.stderr)
    return 1


def run(command: list[str]) -> int:
    require_setup()
    env = dict(os.environ)
    missing = missing_keys(env)
    if not missing:
        os.execvp(command[0], command)
    if env.get(FROM_INFISICAL):
        print(f"Infisical {INFISICAL_ENV} {INFISICAL_PATH} lacks: {' '.join(missing)}", file=sys.stderr)
        return 1
    result = with_infisical(env, [sys.executable, __file__, COMMAND_RUN, "--", *command])
    if result is None:
        print(how_to_fix(missing), file=sys.stderr)
        return 1
    return result.returncode


def main(argv: list[str]) -> int:
    command, rest = (argv[0], argv[1:]) if argv else ("", [])
    if command == COMMAND_REQUIRE_SETUP:
        require_setup()
        return 0
    if command == COMMAND_CHECK:
        return check()
    if command == COMMAND_HAS_KEYS:
        return 0 if not missing_keys(dict(os.environ)) else 1
    if command == COMMAND_RUN and rest:
        return run(rest[1:] if rest[0] == "--" else rest)
    print(__doc__, file=sys.stderr)
    return USAGE_EXIT


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
