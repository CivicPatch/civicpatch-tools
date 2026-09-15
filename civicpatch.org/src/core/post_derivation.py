"""What one scrape's roster implies about a jurisdiction's posts.

Pure — people and taxonomy in, derived posts out, no I/O — so it can be replayed over
history and diffed against what was stored, the same property `people_roles` was
written for.

A post is `(role, division)` and nothing else. Whatever a label carries beyond those two is
per-person and belongs on the membership, so it never appears here.
"""

from pydantic import BaseModel
from shared.schemas import Role
from shared.utils.taxonomy import Taxonomy

from core.membership_label import MembershipLabel, derive_post_label, render
from core.people_roles import DerivedRoles, derive_roles

# A label resolving to no role still gets a post, so nobody is postless. Seeded by 118.
UNMATCHED_ROLE_ID = "unmatched"


class RosterEntry(BaseModel):
    """A roster row, narrowed to what `derived_posts` reads. `post_id` is for `picks_in`."""

    id: str = ""
    jurisdiction_ocdid: str
    labels: list[str] = []
    start_date: str | None = None
    end_date: str | None = None
    post_id: str | None = None


class DerivedMembership(BaseModel):
    """One person a scrape found on a post, and what their label carried besides the role."""

    person_id: str
    designations: list[str] = []
    unmatched_text: list[str] = []
    # The labels the parser consumed
    source_labels: list[str] = []
    role_ids: list[str] = []
    # The source's words for whatever the post label will not say.
    label: str | None = None
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

    Compared on the post's actual role id, not on the parse's winner: when a human picked the
    post, the role the parse would have chosen is itself demoted, and dropping it would lose
    that the source ever said it.

    Only known ids: `membership_roles.role_id` is a foreign key, so an unrecognised role has
    nowhere to go and stays in `unmatched_text`, which is where triage can act on it.

    Order follows `parsed.roles`, which `derive_roles` builds in the order the text gives
    them, so a reader sees them as the source wrote them.
    """
    return [
        (label, ids_by_label[label])
        for label in parsed.roles
        if label in ids_by_label and ids_by_label[label] != post_role_id
    ]


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
    ids_by_label: dict[str, str],
    labels_by_id: dict[str, str],
    post_role_id: str,
    post_division_ocdid: str,
) -> "DerivedMembership":
    """One person: designations, demoted roles and residue beyond the post's own role, plus
    a composed `label` that repeats the post's own name on top of those, so it reads on its
    own."""
    demoted = _demoted_roles(parsed, ids_by_label, post_role_id)
    return DerivedMembership(
        person_id=record.id,
        designations=parsed.other_designations,
        unmatched_text=_unresolved_text(parsed),
        source_labels=parsed.labels,
        role_ids=[role_id for _, role_id in demoted],
        label=render(
            MembershipLabel(
                post_label=derive_post_label(
                    _role_label(post_role_id, labels_by_id), post_division_ocdid
                ),
                demoted_roles=[role_label for role_label, _ in demoted],
                designations=parsed.other_designations,
                # `parsed.unmatched` (every part's, whether or not that part matched a role),
                # not `_unresolved_text` — that narrower set is for `unmatched_text` below,
                # which exists for triage and must not include a residue that already found
                # its role (`derive_roles`' "Commissioner Of Public Safety" case).
                unmatched_text=parsed.unmatched,
            )
        ),
        start_date=record.start_date,
        end_date=record.end_date,
    )


# A post a human already chose, by id. Only `(role_id, division_ocdid)` is needed: those are
# the post's identity, and the derivation groups on them.
class ChosenPost(BaseModel):
    role_id: str
    division_ocdid: str


def derived_posts(
    records: list[RosterEntry],
    taxonomy: Taxonomy,
    roles: list[Role],
    chosen_posts: dict[str, ChosenPost] | None = None,
) -> list[DerivedPost]:
    """One entry per distinct (role, division) this scrape produced.

    A record naming a `post_id` skips the parse for *which post*: a human already answered
    that, and re-deriving it from text could only disagree. What the label carried beyond the
    post — designations, demoted roles, residue — still comes from the labels, because a pick
    says where someone serves, not what the source called them.
    """
    ids_by_label = {role.label: role.id for role in roles}
    labels_by_id = {role.id: role.label for role in roles}
    chosen_posts = chosen_posts or {}

    def role_id_for(parsed: DerivedRoles) -> str:
        label = parsed.role
        return (ids_by_label.get(label) if label else None) or UNMATCHED_ROLE_ID

    grouped: dict[tuple[str, str], list[DerivedMembership]] = {}

    for record in records:
        parsed = derive_roles(
            record.labels,
            record.jurisdiction_ocdid,
            taxonomy,
        )
        picked = chosen_posts.get(record.id)
        key = (
            (picked.role_id, picked.division_ocdid)
            if picked
            else (role_id_for(parsed), parsed.division_ocdid)
        )
        grouped.setdefault(key, []).append(
            _member(record, parsed, ids_by_label, labels_by_id, key[0], key[1])
        )

    return [
        DerivedPost(
            role_id=role_id,
            role_label=_role_label(role_id, labels_by_id),
            division_ocdid=division_ocdid,
            headcount=len(members),
            members=members,
        )
        for (role_id, division_ocdid), members in grouped.items()
    ]
