"""What one scrape's roster implies about a jurisdiction's posts.

Pure — people and taxonomy in, derived posts out, no I/O — so it can be replayed over
history and diffed against what was stored, the same property `people_roles` was
written for.

A post is `(role, division)` and nothing else. Whatever a label carries beyond those two is
per-person and belongs on the membership, so it never appears here.
"""

from pydantic import BaseModel
from shared.schemas import Person, Role
from shared.utils.official_fields import office_name_to_labels
from shared.utils.taxonomy import Taxonomy

from core.membership_label import proposed_membership_label
from core.people_roles import derive_roles

# A label resolving to no role still gets a post, so nobody is postless. Seeded by 118.
UNMATCHED_ROLE_ID = "unmatched"


class DerivedMember(BaseModel):
    """One person a scrape found on a post, and what their label carried besides the role."""

    person_id: str
    designations: list[str] = []
    unmatched_text: list[str] = []
    # The labels the parser consumed
    source_labels: list[str] = []
    role_ids: list[str] = []
    # The source's words for whatever the post label will not say.
    label: str | None = None


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
    members: list[DerivedMember]


def _labels(record: Person) -> list[str]:
    """What the source called this person.

    `labels` is what a record carries. `office.name` is those labels joined with " - " at
    ingest, and splitting it back is the round trip being retired.

    The fallback is for rosters written before `labels` rode along. It expires on its own —
    every ingest since carries them, so it stops firing as the pool drains. Not worth a
    backfill to hurry: `data_json` is being retired, and writing to it to delete four lines
    would be work against a table that is going away.
    """
    if record.labels:
        return record.labels
    office = (record.model_extra or {}).get("office") or {}
    return office_name_to_labels(office.get("name") or "")


def _division(record: Person, parsed: dict) -> str:
    """The record's own division wins over the one re-derived from its label.

    Out of `model_extra`: `office` is not a `Person` field, it is the shape being retired. A
    reviewer may have set the division by hand back when the editor offered it as a field, and
    that answer outranks anything re-derived from text.
    """
    office = (record.model_extra or {}).get("office") or {}
    stored = (office.get("division_ocdid") or "").strip()
    return stored or parsed["division_ocdid"]


def _demoted_role_ids(
    parsed: dict, ids_by_label: dict[str, str], post_role_id: str
) -> list[str]:
    """Every role the label named except the one the post is defined by.

    Compared on the post's actual role id, not on the parse's winner: when a human picked the
    post, the role the parse would have chosen is itself demoted, and dropping it would lose
    that the source ever said it.

    Only known ids: `membership_roles.role_id` is a foreign key, so an unrecognised role has
    nowhere to go and stays in `unmatched_text`, which is where triage can act on it.

    Order follows `parsed["roles"]`, which `derive_roles` builds in the order the text gives
    them, so a reader sees them as the source wrote them.
    """
    return [
        ids_by_label[label]
        for label in parsed.get("roles") or []
        if label in ids_by_label and ids_by_label[label] != post_role_id
    ]


def _unresolved_text(parsed: dict) -> list[str]:
    terms = [
        term
        for part in parsed.get("parts") or []
        if not part.get("role")
        for term in part.get("unmatched") or []
    ]
    return list(dict.fromkeys(terms))


def _member(
    record: Person, parsed: dict, ids_by_label: dict[str, str], post_role_id: str
) -> "DerivedMember":
    """One person, and everything their label carried beyond the post's own role."""
    return DerivedMember(
        person_id=record.id,
        designations=parsed.get("other_designations") or [],
        unmatched_text=_unresolved_text(parsed),
        source_labels=parsed.get("labels") or [],
        role_ids=_demoted_role_ids(parsed, ids_by_label, post_role_id),
        label=proposed_membership_label(parsed.get("parts") or []),
    )


# A post a human already chose, by id. Only `(role_id, division_ocdid)` is needed: those are
# the post's identity, and the derivation groups on them.
class ChosenPost(BaseModel):
    role_id: str
    division_ocdid: str


def derived_posts(
    records: list[Person],
    taxonomy: Taxonomy,
    roles: list[Role],
    chosen: dict[str, ChosenPost] | None = None,
) -> list[DerivedPost]:
    """One entry per distinct (role, division) this scrape produced.

    A record naming a `post_id` skips the parse for *which post*: a human already answered
    that, and re-deriving it from text could only disagree. What the label carried beyond the
    post — designations, demoted roles, residue — still comes from the labels, because a pick
    says where someone serves, not what the source called them.
    """
    ids_by_label = {role.label: role.id for role in roles}
    chosen = chosen or {}

    def role_id_for(parsed: dict) -> str:
        label = parsed.get("role")
        return (ids_by_label.get(label) if label else None) or UNMATCHED_ROLE_ID

    grouped: dict[tuple[str, str], list[DerivedMember]] = {}

    for record in records:
        parsed = derive_roles(
            _labels(record),
            record.jurisdiction_ocdid,
            taxonomy,
        )
        picked = chosen.get(record.post_id or "")
        key = (
            (picked.role_id, picked.division_ocdid)
            if picked
            else (role_id_for(parsed), _division(record, parsed))
        )
        grouped.setdefault(key, []).append(
            _member(record, parsed, ids_by_label, key[0])
        )

    labels_by_id = {role.id: role.label for role in roles}
    return [
        DerivedPost(
            role_id=role_id,
            role_label=labels_by_id.get(role_id, role_id),
            division_ocdid=division_ocdid,
            headcount=len(members),
            members=members,
        )
        for (role_id, division_ocdid), members in grouped.items()
    ]
