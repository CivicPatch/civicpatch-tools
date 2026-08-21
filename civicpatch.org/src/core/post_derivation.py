"""What one scrape's roster implies about a jurisdiction's posts.

Pure — Officials and taxonomy in, post specs out, no I/O — so it can be replayed over
history and diffed against what was stored, the same property `source_record_parse` was
written for.

A post is `(role, division)` and nothing else. Whatever a label carries beyond those two is
per-person and belongs on the membership, so it never appears here.
"""

from pydantic import BaseModel
from shared.schemas import Official, Role
from shared.utils.taxonomy import Taxonomy

from core.source_record_parse import parse_record

# A label resolving to no role still gets a post, so nobody is postless. Seeded by 118.
UNMATCHED_ROLE_ID = "unmatched"


class DerivedMember(BaseModel):
    """One person a scrape found on a post, and what their label carried besides the role."""

    person_id: str
    designations: list[str] = []
    unmatched_text: list[str] = []
    # The labels the parser consumed, already split — `office.name` is a rendering of several
    # joined by " - ". Kept as the parts so triage can show the one a term came out of.
    source_labels: list[str] = []


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


def _member(record: Official, parsed: dict) -> "DerivedMember":
    """One person, with the two halves of what their label carried beyond the role."""
    return DerivedMember(
        person_id=record.id,
        designations=parsed.get("other_designations") or [],
        unmatched_text=parsed.get("unmatched") or [],
        source_labels=parsed.get("labels") or [],
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
        parsed = parse_record(record, taxonomy)
        key = (role_id_for(parsed), _division(record, parsed))
        grouped.setdefault(key, []).append(_member(record, parsed))

    return [
        DerivedPost(
            role_id=role_id,
            division_ocdid=division_ocdid,
            headcount=len(members),
            members=members,
        )
        for (role_id, division_ocdid), members in grouped.items()
    ]
