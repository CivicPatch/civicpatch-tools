"""The fold: every fact about one jurisdiction, in; the people it publishes, out.

Each step is a resolver with its own module and tests; this only chains them:

    live_facts → with_person_ids → with_inherited_blanks → canonical_ids → one cluster per canonical id → derive_person
"""

from pydantic import BaseModel
from shared.utils.taxonomy import Taxonomy

from core.images import published_image_url
from core.projection.canonical_ids import SAME_AS, canonical_ids
from core.projection.facts import ClaimKind, EntityType, Facts
from core.projection.field_value import NAME, overridden_source_values
from core.projection.live_facts import live_facts
from core.projection.partial_records import with_inherited_blanks
from core.projection.people import Person, derive_person
from core.projection.person_ids import with_person_ids


class Roster(BaseModel, frozen=True):
    people: tuple[Person, ...] = ()


def derive_roster(facts: Facts, jurisdiction_ocdid: str, taxonomy: Taxonomy) -> Roster:
    """`facts` is what the loader returned: published, cut at as-of, withdraws not yet applied.

    People come back sorted by id so two rebuilds of the same facts agree (R6).
    """

    live = with_inherited_blanks(with_person_ids(live_facts(facts)))
    clusters = person_clusters(live)
    people = [
        derive_person(root_id, clusters[root_id], live, jurisdiction_ocdid, taxonomy)
        for root_id in sorted(clusters.keys())
    ]
    return Roster(people=tuple(people))


def person_clusters(live: Facts) -> dict[str, set[str]]:
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
        and claim.field_path == NAME
        and claim.kind == ClaimKind.ACCEPT
    ]
    clusters: dict[str, set[str]] = {}
    for person_id in named:
        root_id = canonical.get(person_id) or person_id
        clusters.setdefault(root_id, {root_id}).add(person_id)
    return clusters


def overridden_by_person(facts: Facts) -> dict[str, dict[str, object]]:
    """Per person, what the page says where a claim overrode it — the card's lock disclosure."""
    live = with_person_ids(live_facts(facts))
    overridden = {
        root_id: overridden_source_values(members, live)
        for root_id, members in person_clusters(live).items()
    }
    return {person_id: values for person_id, values in overridden.items() if values}


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
