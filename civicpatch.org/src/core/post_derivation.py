"""What one scrape's roster implies about a jurisdiction's posts.

Pure — Officials and taxonomy in, post specs out, no I/O — so it can be replayed over
history and diffed against what was stored, the same property `source_record_parse` was
written for.

A post is `(role, division)` and nothing else. Everything a label leaves over once those two
are taken is per-person residue and belongs on the membership, so it never appears here.
"""

from pydantic import BaseModel

from core.source_record_parse import parse_record
from shared.schemas import Official, Role
from shared.utils.taxonomy import Taxonomy

# A label resolving to no role still gets a post, so nobody is postless. Seeded by 118.
UNMATCHED_ROLE_ID = "unmatched"


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
    # Which people landed here, and the residue each of them carried.
    members: list[tuple[str, str | None]]


def _residue(parsed: dict) -> str | None:
    """Everything the label had left once the role and the division were taken."""
    leftover = [*parsed.get("other_designations", []), *parsed.get("unmatched", [])]
    return " ".join(leftover) or None


def derived_posts(
    records: list[Official], taxonomy: Taxonomy, roles: list[Role]
) -> list[DerivedPost]:
    """One entry per distinct (role, division) this scrape produced.

    `headcount` is 1 for a role marked unique — a town has one mayor, and two people on that
    post is a data error worth flagging rather than a nine-seat council. Otherwise it is how
    many people actually landed there, which is the best floor available: the page cannot say
    how many seats exist, only how many it listed.
    """
    ids_by_label = {role.label: role.id for role in roles}
    unique_labels = {role.label for role in roles if role.is_unique}

    grouped: dict[tuple[str, str], list[tuple[str, str | None]]] = {}
    unique_keys: set[tuple[str, str]] = set()

    for record in records:
        parsed = parse_record(record, taxonomy)
        label = parsed.get("role")
        role_id = ids_by_label.get(label) if label else None
        key = (role_id or UNMATCHED_ROLE_ID, parsed["division_ocdid"])
        grouped.setdefault(key, []).append((record.id, _residue(parsed)))
        if label in unique_labels:
            unique_keys.add(key)

    return [
        DerivedPost(
            role_id=role_id,
            division_ocdid=division_ocdid,
            headcount=1 if (role_id, division_ocdid) in unique_keys else len(members),
            members=members,
        )
        for (role_id, division_ocdid), members in grouped.items()
    ]
