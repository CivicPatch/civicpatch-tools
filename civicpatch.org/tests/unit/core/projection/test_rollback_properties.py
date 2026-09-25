"""P1 and P2: what rolling back has to mean, over generated fact sets.

    P1  rollback(X) derives what would have been derived had X never existed
    P2  rollback(rollback(X)) derives what was there before the rollback

Both are properties of the fold, not of `services/rollback.py`: rolling back is appending a
withdraw per live fact of X, and everything after that is derivation. Testing them here means no
database and no mocks, and a failure points at the rule rather than at the plumbing.

Randomised over a fixed set of seeds rather than with Hypothesis, which is not a dependency of
this workspace. `.scratch/2026-09-19-rollback-simulator.html` does the same thing in JavaScript
with its own seeded generator, and §0 runs it over seeds 1 to 5; this is its Python twin. If
Hypothesis is ever added, these two properties are what it should shrink.
"""

import random
from datetime import datetime, timedelta, timezone

import pytest
from shared.schemas import Role, RoleConfig, RoleStatus
from shared.utils.taxonomy import build_taxonomy

from core.projection.facts import (
    Claim,
    ClaimKind,
    EntityType,
    Facts,
    SourceRecord,
)
from core.projection.roster import derive_roster

_T = datetime(2026, 1, 1, tzinfo=timezone.utc)
_JURISDICTION = "ocd-jurisdiction/country:us/state:tx/place:alpha/government"
_BASE = "ocd-division/country:us/state:tx/place:alpha"
_ORGANIZATION = "council"
_PEOPLE = ["p1", "p2", "p3"]
_LABELS = ["Mayor", "Council Member", "Clerk"]
_NAMES = ["Ada", "Bo", "Cy", "Dee"]

_TAXONOMY = build_taxonomy(
    RoleConfig(
        roles=[
            Role(id="mayor", label="Mayor", status=RoleStatus.ACTIVE, aliases=[], priority=10, is_unique=True),
            Role(id="council-member", label="Council Member", status=RoleStatus.ACTIVE, aliases=[], priority=20, is_unique=False),
            Role(id="clerk", label="Clerk", status=RoleStatus.ACTIVE, aliases=[], priority=30, is_unique=False),
        ]
    )
)
SEEDS = [1, 2, 3, 4, 5]
CHANGESETS_PER_RUN = 4


def _facts_of(rng: random.Random) -> Facts:
    """A few changesets' worth of records and person claims, in a deliberately small space.

    Small on purpose: three people and three labels make collisions --- two records naming the
    same person, a claim on a person some other changeset also touched --- the common case
    rather than a rarity, and those are what make a rollback interesting.
    """
    records: list[SourceRecord] = []
    claims: list[Claim] = []
    for c in range(CHANGESETS_PER_RUN):
        changeset_id = f"c{c}"
        for r in range(rng.randint(0, 2)):
            records.append(
                SourceRecord(
                    id=f"{changeset_id}-r{r}",
                    changeset_id=changeset_id,
                    created_at=_T + timedelta(minutes=10 * c + r),
                    person_id=rng.choice(_PEOPLE),
                    organization_id=_ORGANIZATION,
                    name=rng.choice(_NAMES),
                    label=rng.choice(_LABELS),
                    source_url="https://alpha.example.gov/council",
                )
            )
        for a in range(rng.randint(0, 2)):
            claims.append(
                Claim(
                    id=f"{changeset_id}-a{a}",
                    changeset_id=changeset_id,
                    created_at=_T + timedelta(minutes=10 * c + 5 + a),
                    entity_type=EntityType.PERSON,
                    entity_id=rng.choice(_PEOPLE),
                    field_path="name",
                    kind=ClaimKind.ACCEPT,
                    value=rng.choice(_NAMES),
                )
            )
    return Facts(records=tuple(records), claims=tuple(claims))


def _live_ids_of(facts: Facts, changeset_id: str) -> list[tuple[EntityType, str]]:
    """What a rollback of this changeset would name, the way the service names it."""
    return [
        *(
            (EntityType.SOURCE_RECORD, record.id)
            for record in facts.records
            if record.changeset_id == changeset_id
        ),
        *(
            (EntityType.CLAIM, claim.id)
            for claim in (*facts.claims, *facts.withdraws)
            if claim.changeset_id == changeset_id
        ),
    ]


def _rolled_back(facts: Facts, changeset_id: str, minute: int) -> Facts:
    """`facts` plus one withdraw per live fact of `changeset_id` --- the whole of a rollback."""
    withdraws = [
        Claim(
            id=f"w{minute}-{entity_id}",
            changeset_id=f"rollback-{minute}",
            created_at=_T + timedelta(minutes=minute),
            entity_type=entity_type,
            entity_id=entity_id,
            field_path=None,
            kind=ClaimKind.WITHDRAW,
            value=None,
        )
        for entity_type, entity_id in _live_ids_of(facts, changeset_id)
    ]
    return facts.model_copy(update={"withdraws": (*facts.withdraws, *withdraws)})


def _without(facts: Facts, changeset_id: str) -> Facts:
    return facts.model_copy(
        update={
            "records": tuple(r for r in facts.records if r.changeset_id != changeset_id),
            "claims": tuple(c for c in facts.claims if c.changeset_id != changeset_id),
        }
    )


def _roster(facts: Facts):
    return derive_roster(facts, _JURISDICTION, _TAXONOMY)


@pytest.mark.unit
@pytest.mark.parametrize("seed", SEEDS)
def test_p1_a_rollback_derives_what_never_having_happened_would_have(seed: int):
    rng = random.Random(seed)
    facts = _facts_of(rng)
    for c in range(CHANGESETS_PER_RUN):
        changeset_id = f"c{c}"
        assert _roster(_rolled_back(facts, changeset_id, 100)) == _roster(
            _without(facts, changeset_id)
        ), f"P1 failed for {changeset_id} at seed {seed}"


@pytest.mark.unit
@pytest.mark.parametrize("seed", SEEDS)
def test_p2_undoing_a_rollback_derives_what_was_there_before_it(seed: int):
    """Undo is rolling back the rollback, which is why it needs no machinery of its own."""
    rng = random.Random(seed)
    facts = _facts_of(rng)
    before = _roster(facts)
    for c in range(CHANGESETS_PER_RUN):
        rolled_back = _rolled_back(facts, f"c{c}", 100)
        undone = _rolled_back(rolled_back, f"rollback-100", 200)
        assert _roster(undone) == before, f"P2 failed for c{c} at seed {seed}"
