"""What one scrape's roster implies about a jurisdiction's posts.

Pure — people and taxonomy in, derived posts out, no I/O — so it can be replayed over
history and diffed against what was stored, the same property `people_roles` was
written for.

A post is `(organization, role, division)` and nothing else. Whatever a label carries beyond
those is per-person and belongs on the membership, so it never appears here.
"""

from pydantic import BaseModel
from shared.schemas import Role
from shared.utils.taxonomy import UNMATCHED_ROLE_ID, Taxonomy

from core.membership_label import MembershipLabel, render
from core.people_roles import DerivedRoles, derive_roles


class RosterSighting(BaseModel):
    """One label as a page gave it, with the organization whose extraction produced it."""

    label: str
    # None when rebuilt from a published membership, which keeps no page per label.
    source_url: str | None = None
    organization_id: str


# Roster keys written by `people_roster` from source records, and stripped from client patches by
# `people_edits`: a client-sent label would have no organization behind it.
SIGHTINGS_FIELD = "sightings"
LABELS_FIELD = "labels"


class RosterEntry(BaseModel):
    """A roster row, narrowed to what `derived_posts` reads. `post_id` is for `picks_in`."""

    id: str = ""
    jurisdiction_ocdid: str
    # Empty for a hand-made entry, or a published person whose memberships carry no labels.
    sightings: list[RosterSighting] = []
    start_date: str | None = None
    end_date: str | None = None
    post_id: str | None = None


class MembershipSource(BaseModel):
    """Popolo's source: a page, and the label it gave. `url` is None only on rows 206 backfilled."""

    url: str | None = None
    note: str


class DerivedMembership(BaseModel):
    """One person a scrape found on a post, and what their label carried besides the role."""

    person_id: str
    designations: list[str] = []
    meta_unmatched_text: list[str] = []
    # Every label a source gave for this membership, with its page.
    sources: list[MembershipSource] = []
    role_ids: list[str] = []
    # The source's words for whatever the post label will not say.
    membership_label: str | None = None
    # The source's claim about the tenure, carried from the record. Not `closed_at`, which is
    # ours: when we stopped seeing them, not when they left.
    start_date: str | None = None
    end_date: str | None = None


class DerivedPost(BaseModel):
    """One post a scrape implies, and who it found there.

    Derived, not declared — the distinction the whole model turns on. Not a post row
    either: it may match one that already exists, or describe one that is never written
    because the scrape is dismissed. `members` rides along because the same grouping pass
    produces both; a post does not own its members, memberships do.
    """

    organization_id: str
    role_id: str
    # The role as a reader says it. Carried rather than looked up downstream: a consumer
    # without the taxonomy would otherwise print the slug, which is how "council-member,
    # District 5" reached the review card.
    role_label: str
    division_ocdid: str
    # Only applied when the post is minted. A later scrape finding a different number must
    # not overwrite a figure somebody typed.
    headcount: int
    members: list[DerivedMembership]


def _demoted_roles(
    parsed: DerivedRoles, ids_by_label: dict[str, str], post_role_id: str
) -> list[tuple[str, str]]:
    """Every role the label named except the one the post is defined by, as (label, id) pairs.

    Only known ids: an unrecognised role stays in `meta_unmatched_text`, which is where triage
    can act on it.

    Order follows `parsed.roles`, which `derive_roles` builds in the order the text gives
    them, so a reader sees them as the source wrote them.
    """
    return [
        (label, ids_by_label[label])
        for label in parsed.roles
        if label in ids_by_label and ids_by_label[label] != post_role_id
    ]


def _without_winner(parsed: DerivedRoles) -> DerivedRoles:
    """A pick overrode the parse, so the role it chose is wrong, not a second role they hold.
    The source's wording survives on the membership's `sources`."""
    return parsed.model_copy(
        update={"roles": [label for label in parsed.roles if label != parsed.role]}
    )


def _unresolved_text(parsed: DerivedRoles) -> list[str]:
    """Residue from labels that resolved to no role at all.

    A label that found its role has already said what it means; leftovers beside a known role
    are a designation, not vocabulary we are missing.
    """
    terms = [
        term
        for part in parsed.parts
        if not part.parsed.role
        for term in part.parsed.unmatched
    ]
    return list(dict.fromkeys(terms))


def _role_label(role_id: str, labels_by_id: dict[str, str]) -> str:
    """The role's display label, or the id itself when it names no known role
    (`UNMATCHED_ROLE_ID`, which is never a key in `labels_by_id`)."""
    return labels_by_id.get(role_id, role_id)


def _member(
    record: RosterEntry,
    parsed: DerivedRoles,
    sources: list[MembershipSource],
    ids_by_label: dict[str, str],
    post_role_id: str,
) -> "DerivedMembership":
    """One person: designations, demoted roles and residue beyond the post's own role — what
    their labels said that the post's own name (looked up separately, from its role and
    division) does not."""
    demoted = _demoted_roles(parsed, ids_by_label, post_role_id)
    return DerivedMembership(
        person_id=record.id,
        designations=parsed.other_designations,
        meta_unmatched_text=_unresolved_text(parsed),
        sources=sources,
        role_ids=[role_id for _, role_id in demoted],
        membership_label=render(
            MembershipLabel(
                demoted_roles=[role_label for role_label, _ in demoted],
                designations=parsed.other_designations,
                # `parsed.unmatched` (every part's, whether or not that part matched a role),
                # not `_unresolved_text` — that narrower set is for `meta_unmatched_text` below,
                # which exists for triage and must not include a residue that already found
                # its role (`derive_roles`' "Commissioner Of Public Safety" case).
                meta_unmatched_text=parsed.unmatched,
            )
        ),
        start_date=record.start_date,
        end_date=record.end_date,
    )


class MembershipBinding(BaseModel):
    """One person bound to one post, in the organization that post belongs to."""

    member: DerivedMembership
    organization_id: str
    post_id: str


# A post a human already chose, by id. Its `(organization_id, role_id, division_ocdid)` is the
# post's identity, and the derivation groups on it.
class ChosenPost(BaseModel):
    organization_id: str
    role_id: str
    division_ocdid: str


def _sources_by_organization(record: RosterEntry) -> dict[str, list[MembershipSource]]:
    grouped: dict[str, list[MembershipSource]] = {}
    for sighting in record.sightings:
        sources = grouped.setdefault(sighting.organization_id, [])
        source = MembershipSource(url=sighting.source_url, note=sighting.label)
        if source not in sources:
            sources.append(source)
    return grouped


def derived_posts(
    records: list[RosterEntry],
    taxonomy: Taxonomy,
    roles: list[Role],
    chosen_posts: dict[str, ChosenPost] | None = None,
) -> list[DerivedPost]:
    """One entry per distinct (organization, role, division) this roster produced.

    A person's labels are parsed once per organization that sighted them, so each gets its own
    membership.

    A picked `post_id` replaces the parse for *which post* in its own organization only, or adds
    a membership there if that organization never sighted the person — never all of them, or a
    membership in another organization would close. A human
    already answered that, and re-deriving it from text could only disagree. What the labels
    carried beyond the post — designations, demoted roles, residue — still comes from them,
    because a pick says where someone serves, not what the source called them.
    """
    ids_by_label = {role.label: role.id for role in roles}
    labels_by_id = {role.id: role.label for role in roles}
    chosen_posts = chosen_posts or {}

    def role_id_for(parsed: DerivedRoles) -> str:
        label = parsed.role
        return (ids_by_label.get(label) if label else None) or UNMATCHED_ROLE_ID

    grouped: dict[tuple[str, str, str], list[DerivedMembership]] = {}

    for record in records:
        groups = _sources_by_organization(record)
        picked = chosen_posts.get(record.id)
        if picked:
            groups.setdefault(picked.organization_id, [])

        for organization_id, sources in groups.items():
            labels = list(dict.fromkeys(source.note for source in sources))
            parsed = derive_roles(labels, record.jurisdiction_ocdid, taxonomy)
            if picked and organization_id == picked.organization_id:
                key = (picked.organization_id, picked.role_id, picked.division_ocdid)
                parsed = _without_winner(parsed)
            else:
                key = (organization_id, role_id_for(parsed), parsed.division_ocdid)
            grouped.setdefault(key, []).append(
                _member(record, parsed, sources, ids_by_label, key[1])
            )

    return [
        DerivedPost(
            organization_id=organization_id,
            role_id=role_id,
            role_label=_role_label(role_id, labels_by_id),
            division_ocdid=division_ocdid,
            headcount=len(members),
            members=members,
        )
        for (organization_id, role_id, division_ocdid), members in grouped.items()
    ]
