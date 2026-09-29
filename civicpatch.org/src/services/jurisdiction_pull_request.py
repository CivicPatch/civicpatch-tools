"""Open a pull request changing one jurisdiction's entry in the jurisdictions repo, and track it as
a changeset until a person merges or closes it.

Every `jurisdictions.yml` edit comes through here, a maintainer's url fix and the pipeline's
government government form answer alike; the label says who asked. `JURISDICTIONS_REPO_URL` points at
open-data until the jurisdictions repo exists. After each hourly sync, every open PR's outcome
is recorded: merged is published, closed is rejected.
"""

import logging

import environment
import httpx
import lib.github.api as github_service
import shared.utils.id_utils as id_utils
from core.sources.open_data.paths import jurisdictions_file_path
from lib.github.auth import get_jurisdictions_sync_headers
from lib.github.pull_requests import PrAuthor, open_attributed_pr
from pydantic import BaseModel
from schemas.common import UserRole
from shared.schemas import GovernmentForm, JurisdictionLevel
from shared.utils.layered_config import jurisdiction_config
from shared.utils.statuses import DismissalReason, PullRequestLabel
from shared.utils.yaml_utils import yaml_dump, yaml_load

import core.jurisdiction_patch as jurisdiction_patch
import database.changesets as changesets_db
import database.government_forms as government_forms_db
import database.jurisdiction_configs as jurisdiction_configs_db
import database.publications as publications_db
import database.users as users_db
from core.jurisdiction_patch import JurisdictionPatch
from database.changesets import WaitingPullRequest
from database.users import SYSTEM_USER_ID

logger = logging.getLogger(__name__)


class UnknownJurisdiction(Exception):
    pass


class GovernmentFormNotAtLevel(Exception):
    pass


class NothingToChange(Exception):
    pass


class PullRequestAlreadyOpen(Exception):
    """args[0]: the open pull request's url."""


class PullRequestFailed(Exception):
    pass


class JurisdictionEdit(BaseModel):
    """What to change: top-level fields as a merge patch (absent is untouched, null clears), and
    `extras.government_form`. `sources` go in the PR body."""

    patch: JurisdictionPatch
    government_form: GovernmentForm | None = None
    sources: list[str] = []


class OpenedPullRequest(BaseModel):
    pull_request_number: int
    pull_request_url: str
    changeset_id: str


async def open_jurisdiction_pull_request(
    jurisdiction_ocdid: str, edit: JurisdictionEdit, label: PullRequestLabel, user_id: str
) -> OpenedPullRequest:
    """`user_id` is the person who asked, or the CivicPatch system user for the pipeline; either
    way it is the commit's author and the changeset's creator."""
    await _check_edit(jurisdiction_ocdid, edit)
    waiting = await fetch_open_pull_request(jurisdiction_ocdid)
    if waiting is not None:
        raise PullRequestAlreadyOpen(waiting.pull_request_url)
    number, url = await _open_pr(jurisdiction_ocdid, edit, label, await _author(user_id))
    changeset_id = id_utils.make_id()
    await changesets_db.register_jurisdiction_pull_request_changeset(changeset_id, jurisdiction_ocdid, url, user_id)
    return OpenedPullRequest(pull_request_number=number, pull_request_url=url, changeset_id=changeset_id)


async def fetch_open_pull_request(jurisdiction_ocdid: str) -> WaitingPullRequest | None:
    """The jurisdiction's PR still waiting: open, or merged but not published yet. One someone
    closed is their answer: its changeset is dismissed as rejected, and None is returned."""
    waiting = await changesets_db.get_open_jurisdiction_pull_request(jurisdiction_ocdid)
    if waiting is None:
        return None
    try:
        state = await _pull_request_state(waiting.pull_request_url)
    except httpx.HTTPStatusError as exc:
        raise PullRequestFailed(f"Could not read {waiting.pull_request_url}: {exc}") from exc
    if state is not github_service.PullRequestState.CLOSED:
        return waiting
    await publications_db.dismiss_changeset(waiting.changeset_id, DismissalReason.REJECTED)
    return None


async def has_open_pull_request(jurisdiction_ocdid: str) -> bool:
    """For a run's config. GitHub unreadable counts as waiting: better to skip one question
    than to fail the run."""
    try:
        return await fetch_open_pull_request(jurisdiction_ocdid) is not None
    except PullRequestFailed:
        return True


async def fetch_pull_request_outcomes() -> None:
    """After each hourly sync: a merged PR is published (the sync has just read the merge), a
    closed one rejected. A PR GitHub cannot report on waits for the next run."""
    for waiting in await changesets_db.list_open_jurisdiction_pull_requests():
        try:
            state = await _pull_request_state(waiting.pull_request_url)
        except httpx.HTTPStatusError:
            logger.warning("fetch_pull_request_outcomes: could not read %s", waiting.pull_request_url)
            continue
        if state is github_service.PullRequestState.MERGED:
            await changesets_db.mark_changeset_published(waiting.changeset_id)
        elif state is github_service.PullRequestState.CLOSED:
            await publications_db.dismiss_changeset(waiting.changeset_id, DismissalReason.REJECTED)


def label_for(author_user_id: str, role: str | None) -> PullRequestLabel | None:
    """The PR's author as the label the jurisdictions repo reads: the pipeline's are the system
    user's, a person's carry their role. None: not allowed to open one."""
    if author_user_id == SYSTEM_USER_ID:
        return PullRequestLabel.SYSTEM
    if role == UserRole.ADMINS:
        return PullRequestLabel.ADMIN
    if role == UserRole.MAINTAINERS:
        return PullRequestLabel.MAINTAINER
    return None


def pull_request_body(edit: JurisdictionEdit, level: str) -> str:
    changes = [
        f"- `{field}`: {value if value is not None else '(cleared)'}" for field, value in edit.patch.items()
    ]
    if edit.government_form is not None:
        changes.append(f"- `extras.government_form`: `{edit.government_form.value}` ({level})")
    source_lines = "\n".join(f"- {source}" for source in edit.sources) or "- none given"
    return "Changes:\n" + "\n".join(changes) + f"\n\nSources:\n{source_lines}"


def pull_request_number(pull_request_url: str) -> int:
    """https://github.com/<owner>/<repo>/pull/7 -> 7."""
    return int(pull_request_url.rstrip("/").rsplit("/", 1)[1])


async def _check_edit(jurisdiction_ocdid: str, edit: JurisdictionEdit) -> None:
    if await government_forms_db.get_government_form_inputs(jurisdiction_ocdid) is None:
        raise UnknownJurisdiction(jurisdiction_ocdid)
    if edit.government_form is None:
        return
    parsed = id_utils.parse_jurisdiction_ocdid(jurisdiction_ocdid)
    if parsed.level == JurisdictionLevel.STATE:
        raise GovernmentFormNotAtLevel("a state has no government form")
    config = jurisdiction_config(
        await jurisdiction_configs_db.get_jurisdiction_configs(), parsed.state, parsed.level
    )
    if edit.government_form not in config.country_government_forms:
        raise GovernmentFormNotAtLevel(f"{edit.government_form.value} is not a {parsed.level} government form")


async def _open_pr(
    jurisdiction_ocdid: str, edit: JurisdictionEdit, label: PullRequestLabel, author: PrAuthor
) -> tuple[int, str]:
    env = environment.get_env_vars()
    repo_url = env["JURISDICTIONS_REPO_URL"]
    file_path = jurisdictions_file_path(jurisdiction_ocdid)
    raw = await github_service.get_github_file_contents(file_path, repo_url=repo_url)
    if not raw:
        raise PullRequestFailed(f"Failed to fetch {file_path}")
    doc = yaml_load(raw)
    entry = jurisdiction_patch.find_jurisdiction(doc, jurisdiction_ocdid)
    if entry is None:
        raise UnknownJurisdiction(f"{jurisdiction_ocdid} is not in {file_path}")
    changed = _changed_fields(entry, edit)
    if not changed:
        raise NothingToChange("No changes to publish")
    number, url_or_error = await open_attributed_pr(
        branch_name=f"civicpatch/jurisdiction-edit/{id_utils.make_id()}",
        file_path=file_path,
        content=yaml_dump(_patched(doc, jurisdiction_ocdid, edit)),
        commit_message=f"Update {', '.join(changed)}: {jurisdiction_ocdid}",
        pull_request_title=f"Jurisdiction edit: {entry.get('name') or jurisdiction_ocdid}",
        pull_request_body=pull_request_body(edit, id_utils.parse_jurisdiction_ocdid(jurisdiction_ocdid).level),
        author=author,
        labels=(label,),
        # The jurisdictions-sync bot opens and labels the PR; the regular bot writes the fork.
        repo_url=repo_url,
        headers=await get_jurisdictions_sync_headers(),
        fork_repo_url=env["JURISDICTIONS_FORK_REPO_URL"],
        fork_headers=await github_service.get_default_headers(),
    )
    if number is None:
        raise PullRequestFailed(url_or_error)
    return number, url_or_error


def _patched(doc: dict, jurisdiction_ocdid: str, edit: JurisdictionEdit) -> dict:
    patched = jurisdiction_patch.apply_patch(doc, jurisdiction_ocdid, edit.patch)
    if edit.government_form is None:
        return patched
    return jurisdiction_patch.set_government_form(patched, jurisdiction_ocdid, edit.government_form.value)


def _changed_fields(entry: dict, edit: JurisdictionEdit) -> list[str]:
    """The fields whose value this edit actually changes in the file's current entry."""
    changed = [field for field, value in edit.patch.items() if entry.get(field) != value]
    if (
        edit.government_form is not None
        and jurisdiction_patch.current_government_form(entry) != edit.government_form.value
    ):
        changed.append("government_form")
    return changed


async def _pull_request_state(pull_request_url: str) -> github_service.PullRequestState:
    return await github_service.get_pull_request_state(
        pull_request_number(pull_request_url),
        environment.get_env_vars()["JURISDICTIONS_REPO_URL"],
        await get_jurisdictions_sync_headers(),
    )


async def _author(user_id: str) -> PrAuthor:
    user = await users_db.get_user_by_id(user_id)
    if user is None:
        raise PullRequestFailed(f"No user {user_id} to author the pull request")
    return PrAuthor(name=user["username"] or user["email"], email=user["email"])
