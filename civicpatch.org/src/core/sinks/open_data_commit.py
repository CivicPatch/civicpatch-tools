"""The open-data commit body: which published changesets each committed file carries."""

from pydantic import BaseModel

from shared.utils.statuses import ChangesetKind


class ChangesetAttribution(BaseModel):
    changeset_id: str
    kind: ChangesetKind
    published_by: str | None
    batch_id: str | None


def _describe(attribution: ChangesetAttribution) -> str:
    text = f"{attribution.kind} {attribution.changeset_id}"
    if attribution.published_by:
        text += f" by {attribution.published_by}"
    if attribution.batch_id:
        text += f" (batch {attribution.batch_id})"
    return text


def _line(
    jurisdiction_ocdid: str,
    changeset_ids: list[str],
    attributions: dict[str, ChangesetAttribution],
) -> str:
    # A write that minted no changeset (person delete, post routes) has nothing to name yet.
    known = [
        attributions[changeset_id]
        for changeset_id in sorted(changeset_ids)
        if changeset_id in attributions
    ]
    if not known:
        return jurisdiction_ocdid
    return f"{jurisdiction_ocdid}: " + "; ".join(_describe(attribution) for attribution in known)


def commit_body(
    changeset_ids_by_jurisdiction: dict[str, list[str]],
    attributions: dict[str, ChangesetAttribution],
) -> str:
    return "\n".join(
        _line(jurisdiction_ocdid, changeset_ids, attributions)
        for jurisdiction_ocdid, changeset_ids in sorted(changeset_ids_by_jurisdiction.items())
    )
