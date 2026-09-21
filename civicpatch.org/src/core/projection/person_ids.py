"""Who each record is about."""

from core.projection.facts import EntityType, Facts, latest_first

PERSON_ID = "person_id"


def with_person_ids(facts: Facts) -> Facts:
    """Facts with every record's `person_id` set to the newest live claim about it."""

    def person_id_of(record):
        claims = sorted(
            [
                claim
                for claim in facts.claims
                if claim.entity_type == EntityType.SOURCE_RECORD
                and claim.entity_id == record.id
                and claim.field_path == PERSON_ID
            ],
            key=latest_first,
        )
        return claims[-1].value if claims else record.person_id

    return facts.model_copy(
        update={
            "records": tuple(
                record.model_copy(update={"person_id": person_id_of(record)})
                for record in facts.records
            )
        }
    )
