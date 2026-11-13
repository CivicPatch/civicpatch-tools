"""What setup needs from the developer's gh login. Permissions are theirs to grant: setup names the command and stops."""
import subprocess

from dev_env import action, note, ok, warn

# Checked up front, so a missing one is asked for rather than failed on.
REQUIRED_SCOPES = {"repo": "fork repos into your org and read them", "read:org": "check your org exists"}
SCOPES_HEADER = "x-oauth-scopes:"


def gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout.strip()


def scopes_from_headers(response: str) -> set[str] | None:
    # None when gh signs in another way (a fine-grained token, say) that reports no scopes to check.
    for line in response.splitlines():
        if line.lower().startswith(SCOPES_HEADER):
            return {scope.strip() for scope in line[len(SCOPES_HEADER):].split(",") if scope.strip()}
    return None


def gh_scopes() -> set[str] | None:
    return scopes_from_headers(gh("api", "-i", "user"))


def refresh_command(flag: str, scopes: list[str]) -> str:
    return f"gh auth refresh -h github.com {flag} {','.join(scopes)}"


def ask_for_scopes(scopes: list[str], why: str) -> None:
    # Permissions are the user's to grant: say exactly what to run, then stop.
    warn(f"gh is missing: {', '.join(scopes)}")
    note(why)
    action(1, f"Run: {refresh_command('-s', scopes)}")
    action(2, "Run mise run setup again")
    raise SystemExit(1)


def ensure_scopes() -> None:
    scopes = gh_scopes()
    missing = [scope for scope in REQUIRED_SCOPES if scopes is not None and scope not in scopes]
    if missing:
        ask_for_scopes(missing, "Needed to " + "; ".join(REQUIRED_SCOPES[scope] for scope in missing) + ".")
    ok("gh permissions")
