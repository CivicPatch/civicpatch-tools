"""Give a developer their own GitHub setup for the civicpatch.org dev stack, shaped like prod: an org
`dev-cp-<login>` holding forks of CivicPatch's public repos and two GitHub Apps standing in for prod's two
bots, then store the Apps' credentials. Needs no access to the CivicPatch org. Browser steps: create the org
(GitHub has no API for it), then Create and Install for each App.

    mise run setup    runs this; writes ../civicpatch.org.env
    --store infisical sends them to Infisical dev /apps/civicpatch instead
"""
import argparse
import base64
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import jwt
from pydantic import BaseModel

from dev_env import action, heading, merge_env_file, note, ok, warn
from gh_auth import ensure_scopes, gh
from github_manifest_flow import CALLBACK_PATH, GITHUB_WEB, HTTP_OK, receive_code

PREFIX = "dev-cp-"
GITHUB_API = "https://api.github.com"
ORG_CREATE_URL = f"{GITHUB_WEB}/account/organizations/new?plan=free"
POLL_SECONDS = 5
WAIT_TIMEOUT_SECONDS = 600
JWT_BACKDATE_SECONDS = 60
JWT_LIFETIME_SECONDS = 540
STORE_ENV_FILE = "env-file"
STORE_INFISICAL = "infisical"
ENV_FILE = Path(__file__).resolve().parents[2] / "civicpatch.org.env"
# Which Infisical comes from your own mise config, never from this repo.
INFISICAL_ENV_KEYS = ("INFISICAL_PROJECT_ID", "INFISICAL_DOMAIN")
INFISICAL_PATH = "/apps/civicpatch"
APP_NAME_MAX = 34  # GitHub's limit; names are unique across all of GitHub, hence the org in each


class DevRepos(BaseModel):
    org: str
    open_data: str
    jurisdictions_fork: str
    jurisdictions: str

    def api_url(self, repo: str) -> str:
        return f"{GITHUB_API}/repos/{self.org}/{repo}"


class AppRole(BaseModel):
    env_prefix: str
    prod_app: str
    uses: str
    permissions: dict[str, str]


class AppCredentials(BaseModel):
    app_id: int
    slug: str
    pem: str
    webhook_secret: str


# The two bots the code reads (environment.py). Labels go through the issues API, hence issues: write.
MAIN_BOT = AppRole(
    env_prefix="GITHUB_", prod_app="civicpatch",
    uses="reads the repos; commits and opens open-data pull requests; pushes each jurisdiction edit's branch "
         "to the jurisdictions fork; opens review-report issues",
    permissions={"contents": "write", "pull_requests": "write", "issues": "write", "metadata": "read"},
)
JURISDICTION_SYNC_BOT = AppRole(
    env_prefix="JURISDICTIONS_SYNC_", prod_app="jurisdiction-sync",
    uses="opens and labels jurisdiction-edit pull requests from the fork on the jurisdictions repo and reads their state",
    permissions={"contents": "read", "pull_requests": "write", "issues": "write", "metadata": "read"},
)
ROLES = (MAIN_BOT, JURISDICTION_SYNC_BOT)


def dev_repos(login: str) -> DevRepos:
    org = f"{PREFIX}{login}"
    return DevRepos(org=org, open_data=f"{org}-open-data", jurisdictions_fork=f"{org}-jurisdictions-fork",
                    jurisdictions=f"{org}-jurisdictions")


def fork_plan(repos: DevRepos) -> list[tuple[str, str]]:
    # (source, name) in order: a fork's parent must exist first, and it is the repo the fork's PRs go into.
    return [
        ("CivicPatch/open-data", repos.open_data),
        ("CivicPatch/jurisdictions", repos.jurisdictions),
        (f"{repos.org}/{repos.jurisdictions}", repos.jurisdictions_fork),
    ]


def app_name(org: str, role: AppRole) -> str:
    return f"{org}-{role.prod_app}"[:APP_NAME_MAX]


def build_manifest(repos: DevRepos, role: AppRole, port: int) -> dict:
    return {
        "name": app_name(repos.org, role),
        "description": f"Dev stand-in for CivicPatch's {role.prod_app} bot in {repos.org}. Used to: {role.uses}. "
                       "Made by mise run setup.",
        "url": f"{GITHUB_WEB}/{repos.org}/{repos.open_data}",
        "redirect_url": f"http://localhost:{port}{CALLBACK_PATH}",
        "public": False,
        "default_permissions": role.permissions,
        "default_events": [],
    }


def installs_for(repos: DevRepos, role: AppRole) -> tuple[str, ...]:
    if role is MAIN_BOT:
        return (repos.open_data, repos.jurisdictions_fork)
    return (repos.jurisdictions,)


def repo_env_values(repos: DevRepos) -> dict[str, str]:
    # Jurisdiction edits target the jurisdictions repo, where they belong. Prod still points them at open-data
    # until the upstream route is built, and until then the code writes open-data's file layout.
    return {
        "OPEN_DATA_REPO_URL": repos.api_url(repos.open_data),
        "JURISDICTIONS_REPO_URL": repos.api_url(repos.jurisdictions),
        "JURISDICTIONS_FORK_REPO_URL": repos.api_url(repos.jurisdictions_fork),
    }


def credential_env_values(role: AppRole, credentials: AppCredentials) -> dict[str, str]:
    values = {
        f"{role.env_prefix}APP_ID": str(credentials.app_id),
        f"{role.env_prefix}APP_PRIVATE_KEY_BASE64": base64.b64encode(credentials.pem.encode()).decode(),
    }
    # An empty secret would let any body pass the HMAC check, so none is better than "".
    if role is MAIN_BOT and credentials.webhook_secret:
        values["GITHUB_WEBHOOK_SECRET"] = credentials.webhook_secret
    return values


def installation_env_values(role: AppRole, installation: int) -> dict[str, str]:
    return {f"{role.env_prefix}APP_INSTALLATION_ID": str(installation)}


def exists(api_path: str) -> bool:
    return subprocess.run(["gh", "api", api_path], capture_output=True).returncode == 0


def wait_until(check, what: str) -> None:
    started = time.time()
    while not check():
        waited = int(time.time() - started)
        if waited > WAIT_TIMEOUT_SECONDS:
            raise SystemExit(f"\nStill no {what} after {WAIT_TIMEOUT_SECONDS} s; run mise run setup again once it's there.")
        # One line rewritten in place, so a long wait shows it is alive.
        print(f"\r  … waiting for {what}: {waited}s (Ctrl+C stops)", end="", flush=True)
        time.sleep(POLL_SECONDS)
    if time.time() - started >= POLL_SECONDS:
        print("\r", end="")


def ensure_org(org: str) -> None:
    if not exists(f"orgs/{org}"):
        warn(f"No org {org} yet")
        action(1, f"Open {ORG_CREATE_URL}")
        action(2, f"Name it {org}, Free plan")
        wait_until(lambda: exists(f"orgs/{org}"), f"org {org}")
    ok(f"org {org}")


def ensure_fork(org: str, source: str, name: str) -> None:
    repo = f"{org}/{name}"
    if not exists(f"repos/{repo}"):
        gh("api", "-X", "POST", f"repos/{source}/forks", "-f", f"organization={org}", "-f", f"name={name}",
           "-F", "default_branch_only=true")
        wait_until(lambda: exists(f"repos/{repo}"), f"fork {repo}")
    # Forks start with Issues off, and the review report opens issues on open-data.
    gh("api", "-X", "PATCH", f"repos/{org}/{name}", "-F", "has_issues=true")
    ok(f"{name} (fork of {source})")


def convert_code(code: str) -> AppCredentials:
    response = httpx.post(f"{GITHUB_API}/app-manifests/{code}/conversions", headers={"Accept": "application/vnd.github+json"})
    response.raise_for_status()
    app = response.json()
    return AppCredentials(app_id=app["id"], slug=app["slug"], pem=app["pem"], webhook_secret=app["webhook_secret"] or "")


def app_jwt(credentials: AppCredentials) -> str:
    now = int(time.time())
    claims = {"iat": now - JWT_BACKDATE_SECONDS, "exp": now + JWT_LIFETIME_SECONDS, "iss": str(credentials.app_id)}
    return jwt.encode(claims, credentials.pem, algorithm="RS256")


def installation_id(credentials: AppCredentials, org: str) -> int | None:
    headers = {"Authorization": f"Bearer {app_jwt(credentials)}", "Accept": "application/vnd.github+json"}
    installations = httpx.get(f"{GITHUB_API}/app/installations", headers=headers).json()
    return next((item["id"] for item in installations if item["account"]["login"] == org), None)


def installed_repos(credentials: AppCredentials, installation: int) -> set[str]:
    headers = {"Authorization": f"Bearer {app_jwt(credentials)}", "Accept": "application/vnd.github+json"}
    token = httpx.post(f"{GITHUB_API}/app/installations/{installation}/access_tokens", headers=headers).json()["token"]
    listing = httpx.get(f"{GITHUB_API}/installation/repositories", params={"per_page": 100},
                        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}).json()
    return {repo["name"] for repo in listing["repositories"]}


def missing_access(credentials: AppCredentials, repos: DevRepos, role: AppRole) -> list[str]:
    installation = installation_id(credentials, repos.org)
    have = installed_repos(credentials, installation) if installation else set()
    return [repo for repo in installs_for(repos, role) if repo not in have]


def install(credentials: AppCredentials, repos: DevRepos, role: AppRole) -> int:
    wanted = ", ".join(installs_for(repos, role))
    if missing := missing_access(credentials, repos, role):
        installation = installation_id(credentials, repos.org)
        page = (f"{GITHUB_WEB}/organizations/{repos.org}/settings/installations/{installation}" if installation
                else f"{GITHUB_WEB}/apps/{credentials.slug}/installations/new")
        warn(f"Missing access: {', '.join(missing)}")
        action(1, f"Open {page}")
        action(2, f"Choose Only select repositories: {wanted}")
        action(3, "Save")
        wait_until(lambda: not missing_access(credentials, repos, role), f"access for {credentials.slug}")
    ok(f"{credentials.slug} on {wanted}")
    return installation_id(credentials, repos.org)


def parse_env(text: str) -> dict[str, str]:
    values = {}
    for line in text.splitlines():
        key, separator, value = line.strip().partition("=")
        if separator and not key.startswith("#"):
            values[key.strip()] = value.strip().strip("'\"")
    return values


def saved_credentials(saved: dict[str, str], repos: DevRepos, role: AppRole) -> AppCredentials | None:
    app_id, pem_base64 = (saved.get(f"{role.env_prefix}{key}") for key in ("APP_ID", "APP_PRIVATE_KEY_BASE64"))
    if not (app_id and pem_base64):
        return None
    webhook_secret = saved.get("GITHUB_WEBHOOK_SECRET", "") if role is MAIN_BOT else ""
    return AppCredentials(app_id=int(app_id), slug=app_name(repos.org, role),
                          pem=base64.b64decode(pem_base64).decode(), webhook_secret=webhook_secret)


def store_env_file(values: dict[str, str]) -> None:
    existing = ENV_FILE.read_text() if ENV_FILE.exists() else ""
    ENV_FILE.write_text(merge_env_file(existing, values))
    ENV_FILE.chmod(0o600)


def load_env_file() -> dict[str, str]:
    return parse_env(ENV_FILE.read_text()) if ENV_FILE.exists() else {}


def infisical_target() -> list[str]:
    project_id, domain = (os.environ.get(key, "") for key in INFISICAL_ENV_KEYS)
    if not (project_id and domain):
        raise SystemExit(f"Set {' and '.join(INFISICAL_ENV_KEYS)} in your own mise config first.")
    return [f"--projectId={project_id}", f"--domain={domain}", "--env=dev", f"--path={INFISICAL_PATH}"]


def load_infisical() -> dict[str, str]:
    exported = subprocess.run(["infisical", "export", "--format=dotenv", *infisical_target()],
                              check=True, capture_output=True, text=True)
    return parse_env(exported.stdout)


def store_infisical(values: dict[str, str]) -> None:
    subprocess.run(["infisical", "secrets", "set", *(f"{key}={value}" for key, value in values.items()), *infisical_target()],
                   check=True, stdout=subprocess.DEVNULL)


def storage_location(store: str) -> str:
    if store == STORE_INFISICAL:
        return f"Infisical (env dev, path {INFISICAL_PATH})"
    return str(ENV_FILE)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--store", choices=[STORE_ENV_FILE, STORE_INFISICAL], default=STORE_ENV_FILE)
    parser.add_argument("--ask", action="store_true", help="ask first; mise run setup passes this")
    args = parser.parse_args()
    # Read back from where setup saves, not the environment, so a rerun sees the same state with either store.
    load, store = (load_infisical, store_infisical) if args.store == STORE_INFISICAL else (load_env_file, store_env_file)
    saved = load()
    all_saved = all(saved.get(f"{role.env_prefix}APP_ID") for role in ROLES)
    question = "Set up your dev GitHub org and Apps? Optional, lets the app update repos. [y/N] "
    # Once both Apps are saved, a rerun only checks them, so it doesn't ask.
    if args.ask and not all_saved and input(question).strip().lower() != "y":
        note("Skipped. Run mise run setup again any time.")
        return
    heading("GitHub setup")
    ensure_scopes()
    repos = dev_repos(gh("api", "user", "--jq", ".login"))
    ensure_org(repos.org)
    for source, name in fork_plan(repos):
        ensure_fork(repos.org, source, name)
    store(repo_env_values(repos))
    # Saved Apps are rechecked, so a rerun picks up where a run stopped and confirms each install.
    for role in ROLES:
        name = app_name(repos.org, role)
        credentials = saved_credentials(saved, repos, role) or convert_code(
            receive_code(repos.org, name, lambda port, role=role: build_manifest(repos, role, port)))
        # GitHub gives the private key out once: save it before anything that can stop the run, like the install wait.
        store(credential_env_values(role, credentials))
        store(installation_env_values(role, install(credentials, repos, role)))
    heading(f"Done. Your GitHub keys are in {storage_location(args.store)}. Restart the dev stack to use them.")


if __name__ == "__main__":
    main()
