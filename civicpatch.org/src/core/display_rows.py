"""The fold's roster as the rows a person reads.

Every human-facing surface renders these: the review card, the batch page, and the sheet
import's note column and report tab. One shape on purpose — three presenters over three shapes
is three chances to tell a volunteer something the card would deny.

Verbatim on purpose too: the shape is the one `database.people`'s `PERSON_JSON` builds, so
moving it to the fold changes where the values come from, not what the browser reads. Pure —
the taxonomy is passed in. `updated_at` is null: the fold has no opinion about it. One reader
exists, `components/review/merge-model.ts`, which takes the newer of two merged records' values
and leaves the key off when neither has one. `updated_at` is not editable, so nothing downstream
reads what it wrote.
"""

from collections.abc import Mapping, Sequence
from types import MappingProxyType

from shared.utils.taxonomy import Taxonomy

from core.membership_label import post_label
from core.projection.facts import PostKey
from core.projection.membership_details import MembershipSource
from core.projection.people import Membership, Person
from core.projection.roster import Roster


def _source_labels(sources: Sequence[MembershipSource]) -> list[str | None]:
    return list(dict.fromkeys(source.note for source in sources))


def _sightings(memberships: Sequence[Membership]) -> list[dict]:
    seen: dict[tuple, dict] = {}
    for membership in memberships:
        for source in membership.sources:
            key = (source.note, source.url, membership.post.organization_id)
            seen.setdefault(
                key,
                {
                    "label": source.note,
                    "source_url": source.url,
                    "organization_id": membership.post.organization_id,
                },
            )
    return list(seen.values())


def _latest(memberships: Sequence[Membership]) -> Membership | None:
    """The tenure the person-level dates and division come from: open first, then most recent.
    Every membership here is open, so it is the most recently first-seen seat."""
    return (
        max(memberships, key=lambda membership: membership.opened_at)
        if memberships
        else None
    )


# The name a human gave a post, keyed by the post's identity. `database.posts._with_label`
# spells the same rule: a derived name is the fallback, not the display name.
PostLabels = Mapping[tuple[str, str, str], str]


def _post_label(post: PostKey, role_label: str, claimed: PostLabels) -> str:
    named = claimed.get((post.organization_id, post.role_id, post.division_ocdid))
    return post_label(role_label, post.division_ocdid, named)


def _membership_row(
    membership: Membership,
    jurisdiction_ocdid: str,
    role_labels: dict[str, str],
    role_priorities: dict[str, int],
    claimed: PostLabels,
) -> dict:
    role_label = role_labels.get(membership.post.role_id, membership.post.role_id)
    return {
        "post_id": membership.post.post_id,
        "organization_id": membership.post.organization_id,
        "role_id": membership.post.role_id,
        "role_label": role_label,
        "priority": role_priorities.get(role_label),
        "jurisdiction_ocdid": jurisdiction_ocdid,
        "division_ocdid": membership.post.division_ocdid,
        "label": membership.label,
        "source_labels": _source_labels(membership.sources),
        "source_urls": sorted(
            {source.url for source in membership.sources if source.url}
        ),
        "designations": list(membership.designations),
        "meta_unmatched_text": list(membership.unmatched_text),
        "start_date": membership.start_date,
        "end_date": membership.end_date,
        "opened_at": membership.opened_at,
        "last_seen_at": membership.last_seen_at,
        "post_label": _post_label(membership.post, role_label, claimed),
    }


def _person_row(
    person: Person,
    jurisdiction_ocdid: str,
    role_labels: dict[str, str],
    role_priorities: dict[str, int],
    claimed: PostLabels,
) -> dict:
    memberships = list(person.memberships)
    latest = _latest(memberships)
    ordered_memberships = sorted(
        memberships,
        key=lambda m: (m.post.role_id, m.post.division_ocdid, m.post.post_id),
    )
    return {
        "id": person.id,
        "name": person.name,
        "other_names": list(person.other_names),
        "phones": list(person.phones),
        "emails": list(person.emails),
        "urls": list(person.urls),
        "source_urls": list(person.source_urls),
        "image": person.image,
        "cdn_image": person.cdn_image,
        "start_date": latest.start_date if latest else None,
        "end_date": latest.end_date if latest else None,
        "jurisdiction_ocdid": jurisdiction_ocdid,
        "updated_at": None,
        # Sorted, as `PERSON_LABELS`' `jsonb_agg(DISTINCT ...)` is.
        "labels": sorted(
            _source_labels(
                [source for membership in memberships for source in membership.sources]
            ),
            key=lambda label: (label is None, label or ""),
        ),
        "sightings": _sightings(memberships),
        "division_ocdid": latest.post.division_ocdid if latest else None,
        "memberships": [
            _membership_row(
                membership, jurisdiction_ocdid, role_labels, role_priorities, claimed
            )
            for membership in ordered_memberships
        ],
    }


def display_rows(
    roster: Roster,
    jurisdiction_ocdid: str,
    taxonomy: Taxonomy,
    claimed_post_labels: PostLabels = MappingProxyType({}),
) -> list[dict]:
    role_labels = {role_id: label for label, role_id in taxonomy.role_ids.items()}
    return [
        _person_row(
            person,
            jurisdiction_ocdid,
            role_labels,
            taxonomy.role_priority,
            claimed_post_labels,
        )
        for person in sorted(roster.people, key=lambda person: (person.name or "", person.id))
    ]
