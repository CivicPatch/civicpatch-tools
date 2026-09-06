"""The roster as open-data receives it: one YAML file per jurisdiction, in git.

The first sink, beside `sinks.sheet` and `sinks.parquet`. Same three jobs each of them does —
render the rows, name the target, write it — and the same content gate, so a sweep that
re-selects an unchanged jurisdiction makes no request at all.

What is different here is that the output is a **diff**. A file in git is read as what changed
since the last commit, so anything that reorders without meaning shows up as a change somebody
has to look at. That is why this module sorts at its own boundary rather than inheriting a
query's `ORDER BY`, and why the unordered lists are sorted too: a query is free to change its
mind, a published file is not.

Extracted from `services/publish.py` on 2026-09-04. That module is the *publish path* — the
review decision, the database writes — and this is one of three places the result is mirrored
to. They were one file because git used to be the only mirror.
"""

import logging

import lib.github.api as github_service
import lib.github.git_data as git_data
import shared.utils.id_utils
from core.membership_label import derive_post_label
from core.output_hash import hash_text
from database import output_hashes as output_hashes_db
from database.people import get_roster
from database.publications import record_change_url
from database.roles import get_roles
from lib.temporal.types import OpenDataBatchCommitRequest, OpenDataCommitItem
from shared.schemas import DerivedPerson, OpenStatesPersonRecord, RoleConfig
from shared.utils.people_utils import person_sort_key
from shared.utils.taxonomy import Taxonomy, build_taxonomy
from shared.utils.yaml_utils import yaml_dump

logger = logging.getLogger(__name__)


async def _taxonomy() -> Taxonomy:
    return build_taxonomy(RoleConfig(roles=await get_roles()))


# Every list whose order carries no meaning. Sorted at this boundary so the same values always
# render the same way: `core.people_edits` builds these as `kept + accepted` — stored array order
# then assertion order — so accepting a value a reviewer already had could reorder the list and
# diff a file that did not change.
_UNORDERED_LISTS = ("other_names", "phones", "emails", "urls", "source_urls")

# An unranked role sorts last, matching `core.people_roles`.
_UNRANKED = 1_000_000


def _role_rank(role: dict) -> tuple:
    """Order of a person's own seats. Priority first — a mayor leads a council member — then
    stable tiebreaks. Not `person_sort_key`, which orders people against each other."""
    priority = role.get("priority")
    return (
        _UNRANKED if priority is None else priority,
        role.get("role_id") or "",
        role.get("division_ocdid") or "",
        role.get("name") or "",
    )


# Needed to build the record, absent from the published one. `jurisdiction_ocdid` lives on
# `PersonBase` because every other consumer of that model wants it — but in the published file
# it belongs to each role, so a person with seats in two places is describable.
_PERSON_ONLY_KEYS = {"jurisdiction_ocdid"}


def _as_published(person: dict) -> dict:
    """The projection's key names translated to the published ones.

    Only `memberships` → `roles` differs today. Explicit, because Pydantic would otherwise
    ignore the unknown key and leave `roles` empty — publishing every person with no seats and
    no error."""
    seats = person.get("memberships")
    if seats is None:
        return person
    roles = [
        {
            **seat,
            # The seat's own name, not the bare role: "Council Member, District 5".
            "name": derive_post_label(
                seat.get("role_label") or "", seat.get("division_ocdid") or ""
            ),
        }
        for seat in seats
    ]
    # Sorted here rather than inherited from `PERSON_MEMBERSHIPS`'s ORDER BY, for the same
    # reason the records are: a query is free to change its mind, a published file is a diff.
    roles.sort(key=_role_rank)

    published = {k: v for k, v in person.items() if k != "memberships"}
    for field in _UNORDERED_LISTS:
        values = published.get(field)
        if values:
            published[field] = sorted(values)
    return {**published, "roles": roles}


def open_data_records(roster: list[dict], taxonomy: Taxonomy) -> list[dict]:
    """The roster as open-data receives it. A key the model does not declare is dropped here.

    **Sorted here, not upstream.** Every caller happens to pass a `get_roster` result, which
    orders by name — but that is a query's business, and a file in git is a diff. If the order
    is only inherited, then changing an ORDER BY anywhere rewrites every published file for no
    reason anybody could see from the change. This is the boundary that owns the output, so it
    is the boundary that sorts.

    `id` breaks the tie: two people can share a name, and without a total order they could swap
    places between commits and show up as a diff.

    Field order within each record is `OpenStatesPersonRecord`'s declaration order — Pydantic
    dumps in that order and ruamel preserves it. `test_open_data_records` pins it, because
    reordering the model would otherwise churn the whole corpus silently.
    """
    # `person_sort_key`, not a rule of our own: this is the same order the roster read uses,
    # so the published file and the page a reviewer approved agree about who comes first.
    # Built from `labels`, which the projection still carries even though the published record
    # no longer does. `id` breaks a remaining tie so the order is total.
    ordered = sorted(
        roster,
        key=lambda person: (
            person_sort_key(DerivedPerson(**person), taxonomy),
            person.get("id") or "",
        ),
    )
    return [
        OpenStatesPersonRecord(**_as_published(person)).model_dump(
            exclude=_PERSON_ONLY_KEYS
        )
        for person in ordered
    ]


class OpenDataWriteRejected(RuntimeError):
    """The branch would not take the commit. Distinct from having nothing to commit."""


async def commit_rendered_files(
    items: list[OpenDataCommitItem], commit_message: str
) -> str | None:
    contents = {}
    taxonomy = await _taxonomy()
    for item in items:
        roster = await get_roster(jurisdiction_ocdid=item.jurisdiction_ocdid)
        contents[item.file_path] = yaml_dump(open_data_records(roster, taxonomy))

    hashes = {path: hash_text(body) for path, body in contents.items()}
    stored = await output_hashes_db.get_hashes(list(hashes))
    pending = {
        path: body
        for path, body in contents.items()
        if stored.get(path) != hashes[path]
    }
    if not pending:
        return None

    # The count comes from `pending`, not from the caller: the caller knows what it selected,
    # and the gate is what decides how much of that is actually a change.
    commit_url = await git_data.commit_github_files(
        branch_name=github_service.DEFAULT_BRANCH,
        contents=pending,
        commit_message=f"{commit_message} ({len(pending)} jurisdiction(s))",
    )
    if not commit_url:
        raise OpenDataWriteRejected(f"open-data refused {len(pending)} file(s)")

    # Only after the ref moved: recording before it would mark a batch written that never
    # reached the branch, and the retry would then skip it.
    await output_hashes_db.record_hashes({path: hashes[path] for path in pending})
    for item in items:
        if item.file_path not in pending:
            continue
        for changeset_id in item.changeset_ids:
            await record_change_url(changeset_id, commit_url)
    return commit_url


def reviewed_file_path(jurisdiction_ocdid: str) -> str:
    folder = shared.utils.id_utils.jurisdiction_ocdid_to_folder(jurisdiction_ocdid)
    return f"data/{folder}.yml"


async def promote_batch_to_reviewed(batch_id: str, published: dict[str, str]) -> None:
    # avoid circular import: lib.temporal.workflows imports the activities module, which
    # imports this one, so importing the client at module scope closes the loop
    import lib.temporal.client as temporal_client

    if not published:
        return
    await temporal_client.enqueue_open_data_batch_commit(
        OpenDataBatchCommitRequest(
            batch_id=batch_id,
            items=[
                OpenDataCommitItem(
                    file_path=reviewed_file_path(jurisdiction_ocdid),
                    changeset_ids=[changeset_id],
                    jurisdiction_ocdid=jurisdiction_ocdid,
                )
                for changeset_id, jurisdiction_ocdid in sorted(published.items())
            ],
            commit_message=f"Publish ({batch_id})",
        )
    )
