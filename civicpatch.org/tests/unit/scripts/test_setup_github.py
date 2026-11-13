import base64
import importlib.util
import json
import sys
from pathlib import Path

import pytest

# The scripts sit in the repo's scripts/, outside any package: loaded by path, with scripts/ importable for
# their imports of each other.
_SCRIPTS = Path(__file__).resolve().parents[4] / "scripts"
sys.path.insert(0, str(_SCRIPTS))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


setup_github = _load("setup_github")
manifest_flow = _load("github_manifest_flow")
dev_env = _load("dev_env")
gh_auth = _load("gh_auth")

pytestmark = pytest.mark.unit

REPOS = setup_github.dev_repos("ada")


def credentials(webhook_secret="hook-secret"):
    return setup_github.AppCredentials(app_id=42, slug="dev-cp-ada-civicpatch", pem="PEM", webhook_secret=webhook_secret)


def test_names_follow_dev_cp_login():
    assert REPOS.org == "dev-cp-ada"
    assert (REPOS.open_data, REPOS.jurisdictions_fork, REPOS.jurisdictions) == (
        "dev-cp-ada-open-data", "dev-cp-ada-jurisdictions-fork", "dev-cp-ada-jurisdictions")


def test_the_jurisdictions_fork_is_a_fork_of_jurisdictions_made_after_it():
    plan = setup_github.fork_plan(REPOS)
    assert plan[0] == ("CivicPatch/open-data", "dev-cp-ada-open-data")
    assert plan[1] == ("CivicPatch/jurisdictions", "dev-cp-ada-jurisdictions")
    assert plan[2] == ("dev-cp-ada/dev-cp-ada-jurisdictions", "dev-cp-ada-jurisdictions-fork")


def test_each_app_is_named_for_its_prod_bot_within_githubs_limit():
    assert setup_github.app_name("dev-cp-ada", setup_github.MAIN_BOT) == "dev-cp-ada-civicpatch"
    assert setup_github.app_name("dev-cp-ada", setup_github.JURISDICTION_SYNC_BOT) == "dev-cp-ada-jurisdiction-sync"
    assert len(setup_github.app_name("dev-cp-" + "a" * 39, setup_github.MAIN_BOT)) == setup_github.APP_NAME_MAX


def test_manifest_says_what_the_app_is_for_and_asks_no_webhooks():
    manifest = setup_github.build_manifest(REPOS, setup_github.JURISDICTION_SYNC_BOT, 9123)
    assert manifest["redirect_url"] == "http://localhost:9123/callback"
    assert "opens and labels jurisdiction-edit pull requests" in manifest["description"]
    assert manifest["default_events"] == []
    assert manifest["default_permissions"]["contents"] == "read"


def test_manifest_form_creates_the_app_in_the_org_and_escapes_the_manifest():
    form = manifest_flow.manifest_form("dev-cp-ada", {"name": 'a"b'}, "st")
    assert "organizations/dev-cp-ada/settings/apps/new?state=st" in form
    assert json.dumps({"name": 'a"b'}) not in form


def test_edits_branch_on_the_fork_and_land_on_jurisdictions():
    values = setup_github.repo_env_values(REPOS)
    assert values["OPEN_DATA_REPO_URL"] == "https://api.github.com/repos/dev-cp-ada/dev-cp-ada-open-data"
    assert values["JURISDICTIONS_REPO_URL"] == "https://api.github.com/repos/dev-cp-ada/dev-cp-ada-jurisdictions"
    assert values["JURISDICTIONS_FORK_REPO_URL"] == "https://api.github.com/repos/dev-cp-ada/dev-cp-ada-jurisdictions-fork"


def test_the_main_bot_is_installed_where_it_writes_and_the_sync_bot_only_on_jurisdictions():
    assert setup_github.installs_for(REPOS, setup_github.MAIN_BOT) == ("dev-cp-ada-open-data", "dev-cp-ada-jurisdictions-fork")
    assert setup_github.installs_for(REPOS, setup_github.JURISDICTION_SYNC_BOT) == ("dev-cp-ada-jurisdictions",)


def test_env_values_use_each_bots_prefix():
    values = setup_github.credential_env_values(setup_github.JURISDICTION_SYNC_BOT, credentials())
    assert values["JURISDICTIONS_SYNC_APP_ID"] == "42"
    assert base64.b64decode(values["JURISDICTIONS_SYNC_APP_PRIVATE_KEY_BASE64"]).decode() == "PEM"
    assert "GITHUB_WEBHOOK_SECRET" not in values
    installation = setup_github.installation_env_values(setup_github.JURISDICTION_SYNC_BOT, 7)
    assert installation == {"JURISDICTIONS_SYNC_APP_INSTALLATION_ID": "7"}


def test_the_main_bot_carries_the_webhook_secret_unless_empty():
    main = setup_github.MAIN_BOT
    assert setup_github.credential_env_values(main, credentials())["GITHUB_WEBHOOK_SECRET"] == "hook-secret"
    assert "GITHUB_WEBHOOK_SECRET" not in setup_github.credential_env_values(main, credentials(webhook_secret=""))


def test_merge_env_file_replaces_keys_and_keeps_the_rest():
    merged = dev_env.merge_env_file("OTHER=1\nGITHUB_APP_ID=old\n", {"GITHUB_APP_ID": "42"})
    assert merged == "OTHER=1\nGITHUB_APP_ID=42\n"


def test_code_from_paste_needs_this_runs_state():
    url = "http://localhost:8765/callback?code=abc&state=st"
    assert manifest_flow.code_from_paste(url, "st") == "abc"
    assert manifest_flow.code_from_paste(url, "other") is None
    assert manifest_flow.code_from_paste("not a url", "st") is None


def test_ask_for_keys_keeps_what_was_pasted_and_skips_blanks(monkeypatch):
    answers = iter(["  sk-or-xyz  ", ""])
    monkeypatch.setattr(dev_env.getpass, "getpass", lambda _prompt: next(answers))
    assert dev_env.ask_for_keys(["OPEN_ROUTER_TOKEN", "GOOGLE_GEMINI_TOKEN"]) == {"OPEN_ROUTER_TOKEN": "sk-or-xyz"}


def test_save_env_file_merges_and_is_readable_only_by_its_owner(tmp_path):
    path = tmp_path / "pipelines.env"
    path.write_text("OTHER=1\n")
    dev_env.save_env_file(path, {"OPEN_ROUTER_TOKEN": "k"})
    assert path.read_text() == "OTHER=1\nOPEN_ROUTER_TOKEN=k\n"
    assert path.stat().st_mode & 0o777 == 0o600


def test_scopes_come_from_ghs_response_headers():
    response = "HTTP/2.0 200 OK\nX-Oauth-Scopes: gist, read:org, repo\n\n{}"
    assert gh_auth.scopes_from_headers(response) == {"gist", "read:org", "repo"}


def test_no_scopes_header_means_nothing_to_check():
    assert gh_auth.scopes_from_headers("HTTP/2.0 200 OK\n\n{}") is None


def test_parse_env_reads_plain_and_quoted_values_and_skips_comments():
    text = "# note\nA=1\nB='two'\nC=\"three\"\n\nnot a line\n"
    assert setup_github.parse_env(text) == {"A": "1", "B": "two", "C": "three"}


def test_saved_credentials_need_both_id_and_key():
    key = base64.b64encode(b"PEM").decode()
    saved = {"JURISDICTIONS_SYNC_APP_ID": "42", "JURISDICTIONS_SYNC_APP_PRIVATE_KEY_BASE64": key}
    found = setup_github.saved_credentials(saved, REPOS, setup_github.JURISDICTION_SYNC_BOT)
    assert (found.app_id, found.pem, found.slug) == (42, "PEM", "dev-cp-ada-jurisdiction-sync")
    assert setup_github.saved_credentials({"JURISDICTIONS_SYNC_APP_ID": "42"}, REPOS, setup_github.JURISDICTION_SYNC_BOT) is None


def test_storage_location_names_the_env_file_or_the_infisical_path():
    assert setup_github.storage_location(setup_github.STORE_ENV_FILE) == str(setup_github.ENV_FILE)
    assert setup_github.storage_location(setup_github.STORE_INFISICAL) == "Infisical (env dev, path /apps/civicpatch)"
