"""Which post a deleted post's facts now belong to.

Deleting a post files a `same_as` claim on it, valued the post that takes its memberships, like
a person merge; the target has the same role and division in another organization. Its records, `posts` claims
and membership claims are read as the target's, in memory only: facts stay append-only (R1).
"""

from collections.abc import Iterable

from shared.utils.membership_ids import membership_id
from shared.utils.taxonomy import Taxonomy

from core.people_edits import POSTS_FIELD
from core.projection.canonical_ids import SAME_AS, canonical_ids
from core.projection.facts import Claim, EntityType, Facts, PostKey, SourceRecord
from core.projection.posts import parse_labels, post_keys


def with_post_merges(facts: Facts, jurisdiction_ocdid: str, taxonomy: Taxonomy) -> Facts:
    merged_into = post_merges(facts, jurisdiction_ocdid, taxonomy)
    if not merged_into:
        return facts
    return facts.model_copy(
        update={
            "records": _records_merged(facts.records, merged_into, jurisdiction_ocdid, taxonomy),
            "claims": _claims_merged(facts, merged_into),
        }
    )


def post_merges(facts: Facts, jurisdiction_ocdid: str, taxonomy: Taxonomy) -> dict[PostKey, PostKey]:
    """Every deleted post's key, mapped to the post it reads as. A chain resolves to its end."""
    merges: list[tuple[Claim, PostKey]] = []
    for claim in facts.claims:
        if claim.entity_type == EntityType.POST and claim.field_path == SAME_AS and claim.post is not None:
            merges.append((claim, claim.post))
    if not merges:
        return {}
    keys_by_id = {key.post_id: key for key in _known_keys(facts, jurisdiction_ocdid, taxonomy)}
    for _, target in merges:
        keys_by_id[target.post_id] = target
    # Only a same office in another organization: records are re-read by organization alone.
    same_office = [
        claim
        for claim, target in merges
        if claim.entity_id in keys_by_id and _same_office(keys_by_id[claim.entity_id], target)
    ]
    roots = canonical_ids(same_office)
    return {keys_by_id[old_id]: keys_by_id[root_id] for old_id, root_id in roots.items()}


def _same_office(old: PostKey, target: PostKey) -> bool:
    return (old.role_id, old.division_ocdid) == (target.role_id, target.division_ocdid)


def _known_keys(facts: Facts, jurisdiction_ocdid: str, taxonomy: Taxonomy) -> set[PostKey]:
    from_records = set(post_keys(facts.records, jurisdiction_ocdid, taxonomy))
    from_claims = {claim.post for claim in facts.claims if claim.post is not None}
    return from_records | from_claims


def _records_merged(
    records: tuple[SourceRecord, ...],
    merged_into: dict[PostKey, PostKey],
    jurisdiction_ocdid: str,
    taxonomy: Taxonomy,
) -> tuple[SourceRecord, ...]:
    """Batched as `post_keys` batches: one person's records from one read of one organization."""
    batches: dict[tuple[str, str, str], list[SourceRecord]] = {}
    for record in records:
        batches.setdefault((record.changeset_id, record.organization_id, record.person_id), []).append(record)
    organization_by_record: dict[str, str] = {}
    for batch in batches.values():
        key, _ = parse_labels(batch, jurisdiction_ocdid, taxonomy)
        if key in merged_into:
            for record in batch:
                organization_by_record[record.id] = merged_into[key].organization_id
    return tuple(
        record.model_copy(update={"organization_id": organization_by_record[record.id]})
        if record.id in organization_by_record
        else record
        for record in records
    )


def _claims_merged(facts: Facts, merged_into: dict[PostKey, PostKey]) -> tuple[Claim, ...]:
    post_ids = {old.post_id: new.post_id for old, new in merged_into.items()}
    membership_ids = _membership_ids_merged(_person_ids(facts), post_ids)
    return tuple(_claim_merged(claim, merged_into, post_ids, membership_ids) for claim in facts.claims)


def _claim_merged(
    claim: Claim,
    merged_into: dict[PostKey, PostKey],
    post_ids: dict[str, str],
    membership_ids: dict[str, str],
) -> Claim:
    if claim.field_path == POSTS_FIELD and claim.post in merged_into:
        target = merged_into[claim.post]
        return claim.model_copy(update={"post": target, "value": target.post_id})
    if claim.entity_type == EntityType.MEMBERSHIP and claim.entity_id in membership_ids:
        return claim.model_copy(update={"entity_id": membership_ids[claim.entity_id]})
    if claim.entity_type == EntityType.POST and claim.field_path != SAME_AS and claim.entity_id in post_ids:
        return claim.model_copy(update={"entity_id": post_ids[claim.entity_id]})
    return claim


def _person_ids(facts: Facts) -> set[str]:
    from_records = {record.person_id for record in facts.records}
    from_claims = {claim.entity_id for claim in facts.claims if claim.entity_type == EntityType.PERSON}
    return from_records | from_claims


def _membership_ids_merged(person_ids: Iterable[str], post_ids: dict[str, str]) -> dict[str, str]:
    """`membership_id(person, post)` is a hash, so a membership claim is re-keyed by computing
    every person's id on the old post and on its target."""
    return {
        membership_id(person_id, old_post_id): membership_id(person_id, new_post_id)
        for person_id in person_ids
        for old_post_id, new_post_id in post_ids.items()
    }
