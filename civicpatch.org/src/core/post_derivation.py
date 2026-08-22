"""What one scrape's roster implies about a jurisdiction's posts.

Pure — Officials and taxonomy in, post specs out, no I/O — so it can be replayed over
history and diffed against what was stored, the same property `source_record_parse` was
written for.

A post is `(role, division)` and nothing else. Whatever a label carries beyond those two is
per-person and belongs on the membership, so it never appears here.
"""

from pydantic import BaseModel
from shared.schemas import Official, Role
from shared.utils.official_fields import office_name_to_labels
from shared.utils.taxonomy import Taxonomy

from core.membership_label import proposed_membership_label
from core.source_record_parse import parse_record

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
    division_ocdid: str
    # Only applied when the post is minted. A later scrape finding a different number must
    # not overwrite a figure somebody typed.
    headcount: int
    members: list[DerivedMember]


def _division(record: Official, parsed: dict) -> str:
    """The Record's own division wins over the one re-derived from its label."""
    stored = (record.office.division_ocdid or "").strip()
    return stored or parsed["division_ocdid"]


def _demoted_role_ids(parsed: dict, ids_by_label: dict[str, str]) -> list[str]:
    """Every role the label named except the one defining the post.

    Only known ids: `membership_roles.role_id` is a foreign key, so an unrecognised role has
    nowhere to go and stays in `unmatched_text`, which is where triage can act on it.

    Order follows `parsed["roles"]`, which `parse_record` builds in the order the text gives
    them, so a reader sees them as the source wrote them.
    """
    winner = parsed.get("role")
    return [
        ids_by_label[label]
        for label in parsed.get("roles") or []
        if label != winner and label in ids_by_label
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
    record: Official, parsed: dict, ids_by_label: dict[str, str]
) -> "DerivedMember":
    """One person, and everything their label carried beyond the post's own role."""
    return DerivedMember(
        person_id=record.id,
        designations=parsed.get("other_designations") or [],
        unmatched_text=_unresolved_text(parsed),
        source_labels=parsed.get("labels") or [],
        role_ids=_demoted_role_ids(parsed, ids_by_label),
        label=proposed_membership_label(parsed.get("parts") or [], parsed.get("role")),
    )


def derived_posts(
    records: list[Official], taxonomy: Taxonomy, roles: list[Role]
) -> list[DerivedPost]:
    """One entry per distinct (role, division) this scrape produced."""
    ids_by_label = {role.label: role.id for role in roles}

    def role_id_for(parsed: dict) -> str:
        label = parsed.get("role")
        return (ids_by_label.get(label) if label else None) or UNMATCHED_ROLE_ID

    grouped: dict[tuple[str, str], list[DerivedMember]] = {}

    for record in records:
        parsed = parse_record(
            office_name_to_labels(record.office.name),
            record.jurisdiction_ocdid,
            taxonomy,
        )
        key = (role_id_for(parsed), _division(record, parsed))
        grouped.setdefault(key, []).append(_member(record, parsed, ids_by_label))

    return [
        DerivedPost(
            role_id=role_id,
            division_ocdid=division_ocdid,
            headcount=len(members),
            members=members,
        )
        for (role_id, division_ocdid), members in grouped.items()
    ]
