"""The `parsed` half of a source_record: what one submitted Record decomposes into.

Pure — taxonomy in, structure out, no I/O — so a parser fix can be replayed over history and
diffed against what was stored without touching the database.

`parsed` holds the structured *decision*, not its rendering. `office.name` is already the
rendering and already lives on `people.data`; storing it again here would duplicate current
state instead of recording the thing kept nowhere else: which role won, which division was
resolved, and which labels resolved to nothing.
"""

from shared.schemas import Official
from shared.utils.label_parser import ParsedLabel, division_ocdid, parse_label
from shared.utils.official_fields import office_name_to_labels
from shared.utils.taxonomy import Taxonomy


def parse_record(record: Official, taxonomy: Taxonomy) -> dict:
    """The derivation for one Record, as stored in `source_records.parsed`.

    Read from `office.name` rather than a structured field because that string is all the
    Record carries — splitting it back into labels is the first lossy step being recorded.
    """
    labels = office_name_to_labels(record.office.name)
    parsed = [parse_label(label, taxonomy) for label in labels]
    return {
        "labels": labels,
        "role": _winning_role(parsed, taxonomy),
        "roles": _unique([role for p in parsed for role in p.roles]),
        "division_ocdid": _division_ocdid(parsed, record.jurisdiction_ocdid),
        "other_designations": _unique(
            [d for p in parsed for d in p.other_designations]
        ),
        "unmatched": _unique([term for p in parsed for term in p.unmatched]),
    }


def _winning_role(parsed: list[ParsedLabel], taxonomy: Taxonomy) -> str | None:
    """The role published after the usurp — highest priority across every label."""
    roles = [p.role for p in parsed if p.role]
    if not roles:
        return None
    return min(roles, key=lambda role: (taxonomy.role_priority.get(role, 1_000_000), role))


def _division_ocdid(parsed: list[ParsedLabel], jurisdiction_ocdid: str) -> str:
    """A person sits in at most one division; the first label naming one decides it."""
    located = next((p for p in parsed if p.division), None)
    return division_ocdid(located or ParsedLabel(), jurisdiction_ocdid)


def _unique(values: list[str]) -> list[str]:
    """Order-preserving, so the stored derivation reads the way the label did."""
    return list(dict.fromkeys(values))
