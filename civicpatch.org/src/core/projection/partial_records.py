"""A partial record states only the cells it filled, so its blanks keep the last stated value."""

from core.projection.facts import Facts, SourceRecord, latest_first

INHERITED_FIELDS = (
    "label",
    "other_names",
    "url",
    "phone",
    "email",
    "image",
    "cdn_image",
    "start_date",
    "end_date",
)


def _blank(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, tuple):
        return not value
    return False


def _stated(record: SourceRecord) -> dict[str, object]:
    return {
        field: getattr(record, field)
        for field in INHERITED_FIELDS
        if not _blank(getattr(record, field))
    }


def _carried_into(record: SourceRecord, carried: dict[str, object]) -> SourceRecord:
    inherited = {
        field: carried[field]
        for field in INHERITED_FIELDS
        if field in carried and _blank(getattr(record, field))
    }
    return record.model_copy(update=inherited) if inherited else record


def with_inherited_blanks(facts: Facts) -> Facts:
    """Facts whose partial records carry the last stated value into their blank cells."""
    if not any(record.is_partial for record in facts.records):
        return facts

    groups: dict[tuple[str, str], list[SourceRecord]] = {}
    for record in facts.records:
        groups.setdefault((record.person_id, record.organization_id), []).append(record)

    rewritten: dict[str, SourceRecord] = {}
    for group in groups.values():
        carried: dict[str, object] = {}
        for record in sorted(group, key=latest_first):
            if record.is_partial:
                record = _carried_into(record, carried)
            carried = _stated(record)
            rewritten[record.id] = record

    return facts.model_copy(
        update={"records": tuple(rewritten[record.id] for record in facts.records)}
    )
