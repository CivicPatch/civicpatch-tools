"""The fold: every fact about one jurisdiction, in; the people it publishes, out.

Each step is a resolver with its own module and tests; this only chains them:

    live_facts → with_person_ids → canonical_ids → one cluster per canonical id → derive_person
"""

from collections.abc import Sequence

from pydantic import BaseModel
from shared.schemas import Role
from shared.utils.taxonomy import Taxonomy

from core.images import published_image_url
from core.projection.canonical_ids import SAME_AS, canonical_ids
from core.projection.facts import EntityType, Facts
from core.projection.live_facts import live_facts
from core.projection.people import Person, derive_person
from core.projection.person_ids import with_person_ids


class Roster(BaseModel, frozen=True):
    people: tuple[Person, ...] = ()


def derive_roster(
    facts: Facts,
    jurisdiction_ocdid: str,
    taxonomy: Taxonomy,
    roles: Sequence[Role],
) -> Roster:
    """`facts` is what the loader returned: published, cut at as-of, withdraws not yet applied.

    People come back sorted by id so two rebuilds of the same facts agree (R6).
    """

    live = with_person_ids(live_facts(facts))
    same_as = [
        claim
        for claim in live.claims
        if claim.entity_type == EntityType.PERSON and claim.field_path == SAME_AS
    ]
    canonical = canonical_ids(same_as)
    named = [record.person_id for record in live.records] + [
        claim.entity_id
        for claim in live.claims
        if claim.entity_type == EntityType.PERSON
    ]
    clusters: dict[str, set[str]] = {}
    for person_id in named:
        root_id = canonical.get(person_id) or person_id
        clusters.setdefault(root_id, {root_id}).add(person_id)

    people = [
        derive_person(
            root_id, clusters[root_id], live, jurisdiction_ocdid, taxonomy, roles
        )
        for root_id in sorted(clusters.keys())
    ]
    return Roster(people=tuple(people))


def with_published_images(
    roster: Roster, artifacts_bucket: str, friendly_storage_host: str
) -> Roster:
    return Roster(
        people=tuple(
            person.model_copy(
                update={
                    "cdn_image": published_image_url(
                        person.cdn_image, artifacts_bucket, friendly_storage_host
                    )
                }
            )
            for person in roster.people
        )
    )
