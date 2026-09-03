"""Publishing a scrape: making its roster the live one.

The single entry point for "this data is now live", so there is one place to extend rather
than two paths to keep in step. Previously publishing was a side effect of the GitHub merge —
`publish_side_effects` re-read the merged file out of open-data to populate `people` — which
made the repo the authority for what is live and meant a dead merge worker meant stale data.
"""

import logging

import environment
import lib.buckets as buckets
import lib.github.api as github_service
import lib.github.git_data as git_data
import lib.storage as storage_service
import services.change_logs as change_logs
import shared.utils.id_utils
from core.images import artifacts_key, promoted_key, promoted_url
from core.membership_label import derive_post_label
from core.post_derivation import ChosenPost, DerivedPost, RosterEntry, derived_posts
from database import posts as posts_db
from database.database import get_pool
from database.people import get_roster
from database.publications import dismiss_request, publish_request, record_change_url
from database.roles import get_roles
from lib.temporal.types import (
    OpenDataBatchCommitRequest,
    OpenDataCommitItem,
    OpenDataCommitRequest,
)
from shared.schemas import DerivedPerson, OpenStatesPersonRecord, RoleConfig
from shared.utils.people_utils import person_sort_key
from shared.utils.statuses import DismissalReason
from shared.utils.taxonomy import Taxonomy, build_taxonomy
from shared.utils.yaml_utils import yaml_dump

logger = logging.getLogger(__name__)


def promote_images(people: list[dict]) -> list[dict]:
    """Move this roster's photos from the artifacts bucket to the CDN, and point the records
    at their new home. Mutates nothing the caller owns — returns the rewritten roster.

    Runs at publish rather than submit so unreviewed photos never reach the CDN, mirroring
    the data itself: `local-unreviewed` is promoted to `local` by the same act of review.

    A photo that fails to copy is left pointing at the artifacts bucket rather than failing
    the publish — the URL still resolves, it is just not on the permanent host yet.
    """
    friendly_host = environment.get_env_vars()["FRIENDLY_STORAGE_HOST"]
    promoted = []
    for person in people:
        promoted.append(_promote_person_image(person, friendly_host))
    return promoted


def _promote_person_image(person: dict, friendly_host: str) -> dict:
    cdn_image = person.get("cdn_image")
    if not cdn_image:
        return person
    source_key = artifacts_key(cdn_image, buckets.ARTIFACTS)
    if not source_key:
        return person
    dest_key = promoted_key(source_key)
    if not dest_key:
        logger.warning(f"Unexpected artifacts key, not promoting: {source_key}")
        return person
    try:
        storage_service.copy_object(
            buckets.ARTIFACTS, source_key, buckets.CDN, dest_key
        )
    except Exception as e:
        logger.error(f"Failed to promote image {source_key}: {e}", exc_info=True)
        return person
    return {**person, "cdn_image": promoted_url(friendly_host, dest_key)}


def picks_in(roster: list[RosterEntry]) -> dict[str, str]:
    """The post each person was picked for, by person id."""
    return {record.id: record.post_id for record in roster if record.id and record.post_id}


async def chosen_posts(picks: dict[str, str]) -> dict[str, ChosenPost]:
    """The seat a reviewer picked, **by person id**.

    Keyed on the person so the derivation's input can be purely what the source said: a pick is
    a human's answer and travels here instead of riding on the record.

    A pick naming a post that no longer exists is simply absent, and the derivation falls back
    to the labels rather than losing the person.
    """
    if not picks:
        return {}
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        rows = await posts_db.identities_by_id(cur, list(set(picks.values())))
    return {
        person_id: ChosenPost(
            role_id=rows[post_id]["role_id"],
            division_ocdid=rows[post_id]["division_ocdid"],
        )
        for person_id, post_id in picks.items()
        if post_id in rows
    }


async def _taxonomy() -> Taxonomy:
    return build_taxonomy(RoleConfig(roles=await get_roles()))


async def _get_derived_posts(people: list[dict]) -> list[DerivedPost]:
    roles = await get_roles()
    taxonomy = build_taxonomy(RoleConfig(roles=roles))
    roster = [RosterEntry(**person) for person in people]
    return derived_posts(roster, taxonomy, roles, await chosen_posts(picks_in(roster)))


async def publish_people(
    changeset_id: str,
    jurisdiction_ocdid: str,
    people: list[dict],
    resolved_by_user_id: str | None = None,
) -> int:
    """Publish one scrape's roster. Returns the number of people written."""
    written = await publish_request(
        changeset_id,
        jurisdiction_ocdid,
        people,
        resolved_by_user_id,
        derived=await _get_derived_posts(people),
    )
    logger.info(f"[{changeset_id}] Published {written} people for {jurisdiction_ocdid}")
    # Audited here rather than at the caller: publishing is this function, and the previous
    # home for this was the merge worker, which is going away.
    await change_logs.record_publish(changeset_id, resolved_by_user_id)
    return written


async def dismiss_people(
    changeset_id: str, resolved_by_user_id: str | None = None
) -> None:
    """Mark a scrape reviewed-and-not-published. Leaves the roster untouched."""
    # `dismiss_request` writes the close_review log itself now, with the reason — so every
    # dismissal has one, not just the reviewer's. That is what retires `record_close`.
    await dismiss_request(changeset_id, DismissalReason.REJECTED, resolved_by_user_id)
    logger.info(f"[{changeset_id}] Dismissed without publishing")


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


def unreviewed_file_path(jurisdiction_ocdid: str) -> str:
    folder = shared.utils.id_utils.unreviewed_folder(
        shared.utils.id_utils.jurisdiction_ocdid_to_folder(jurisdiction_ocdid)
    )
    return f"data/{folder}.yml"


async def commit_rendered_file(
    file_path: str,
    changeset_id: str | None,
    jurisdiction_ocdid: str,
    commit_message: str,
) -> str | None:
    """Render a file out of the database and write it to open-data.

    The rendering happens here rather than at the caller so every retry produces current
    content: git holds a projection of the database, and a write that lands late should carry
    what is true when it lands, not what was true when it was queued.
    """
    roster = await get_roster(jurisdiction_ocdid=jurisdiction_ocdid)
    taxonomy = await _taxonomy()
    commit_url = await github_service.upsert_github_file(
        branch_name=github_service.DEFAULT_BRANCH,
        file_path=file_path,
        content_str=yaml_dump(open_data_records(roster, taxonomy)),
        commit_message=commit_message,
    )
    if commit_url and changeset_id:
        await record_change_url(changeset_id, commit_url)
    return commit_url


async def commit_rendered_files(
    items: list[OpenDataCommitItem], commit_message: str
) -> str | None:
    """Render every jurisdiction out of the database and write them as one commit.

    Same contract as `commit_rendered_file` one file at a time: rendering happens per attempt,
    so a retry carries what is true when it lands. Every request is stamped with the one commit
    url, because that is genuinely where each of them landed.
    """
    contents = {}
    taxonomy = await _taxonomy()
    for item in items:
        roster = await get_roster(jurisdiction_ocdid=item.jurisdiction_ocdid)
        contents[item.file_path] = yaml_dump(open_data_records(roster, taxonomy))

    commit_url = await git_data.commit_github_files(
        branch_name=github_service.DEFAULT_BRANCH,
        contents=contents,
        commit_message=commit_message,
    )
    if not commit_url:
        return None
    for item in items:
        await record_change_url(item.changeset_id, commit_url)
    return commit_url


def reviewed_file_path(jurisdiction_ocdid: str) -> str:
    folder = shared.utils.id_utils.jurisdiction_ocdid_to_folder(jurisdiction_ocdid)
    return f"data/{folder}.yml"


async def promote_to_reviewed(changeset_id: str, jurisdiction_ocdid: str) -> None:
    """Move a published jurisdiction from the unreviewed path to the canonical one.

    Queued rather than immediate, like every other open-data write: publishing is already a
    fact in the database by the time this runs. The reviewed file renders from `people`, not
    from this scrape — the canonical file is the jurisdiction's live roster, which can include
    people an earlier scrape published.
    """
    # avoid circular import: lib.temporal.workflows imports the activities module, which
    # imports this one, so importing the client at module scope closes the loop
    import lib.temporal.client as temporal_client

    await temporal_client.enqueue_open_data_commit(
        OpenDataCommitRequest(
            file_path=reviewed_file_path(jurisdiction_ocdid),
            changeset_id=changeset_id,
            jurisdiction_ocdid=jurisdiction_ocdid,
            commit_message=f"Publish {jurisdiction_ocdid} ({changeset_id})",
            delete_path=unreviewed_file_path(jurisdiction_ocdid),
            delete_message=f"Promote {jurisdiction_ocdid} out of unreviewed ({changeset_id})",
        )
    )


async def commit_roster(jurisdiction_ocdid: str, commit_message: str) -> None:
    """Mirror a jurisdiction's live roster into open-data after an edit that is not a publish.

    No request id: these edits have no request row, and minting one would make the edit
    supersede the jurisdiction's pending scrape cards.
    """
    # avoid circular import: lib.temporal.workflows imports the activities module, which
    # imports this one, so importing the client at module scope closes the loop
    import lib.temporal.client as temporal_client

    # Writing an empty file over a real one is the one case where stale beats stomped.
    if not await get_roster(jurisdiction_ocdid=jurisdiction_ocdid):
        logger.warning(f"No seated roster for {jurisdiction_ocdid}; not mirroring")
        return

    await temporal_client.enqueue_open_data_commit(
        OpenDataCommitRequest(
            file_path=reviewed_file_path(jurisdiction_ocdid),
            changeset_id=None,
            jurisdiction_ocdid=jurisdiction_ocdid,
            commit_message=commit_message,
        )
    )


async def promote_batch_to_reviewed(
    batch_id: str, published: dict[str, str]
) -> None:
    """One open-data commit for everything a bulk publish made live.

    `published` maps changeset_id to jurisdiction_ocdid — every jurisdiction that reached the
    database, which is not every jurisdiction the reviewer selected: one refusing must not keep
    the rest out of open-data.
    """
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
                    changeset_id=changeset_id,
                    jurisdiction_ocdid=jurisdiction_ocdid,
                )
                for changeset_id, jurisdiction_ocdid in sorted(published.items())
            ],
            commit_message=f"Publish {len(published)} jurisdictions ({batch_id})",
        )
    )
