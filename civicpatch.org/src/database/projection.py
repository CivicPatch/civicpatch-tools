"""The one writer of the projection.

Every row a publish puts in `people`, `memberships` and `membership_roles` is written from
here and nowhere else, so what "publishing a roster" changes is one place to read. Still
upsert-shaped: the statements are the ones the publish path always ran, moved under one roof
unchanged. The delete-and-rebuild writer replaces them at step 8 of the projector plan.

`tests/unit/database/test_one_writer.py` holds the boundary. The writes still outside it are
each named there with the step that deletes them.
"""

import json
from collections.abc import Iterable

from core.post_derivation import MembershipBinding
from core.projection.people import Membership, Person
from core.projection.posts import PostKey
from core.projection.roster import Roster
from database.assertions import LATEST_FIRST
from database.posts import LABEL_FIELD

_PERSON_COLUMNS = (
    "name",
    "other_names",
    "phones",
    "emails",
    "urls",
    "source_urls",
    "image",
    "cdn_image",
)
_LIST_COLUMNS = frozenset({"other_names", "phones", "emails", "urls", "source_urls"})

# One statement, so the writers cannot quietly stop agreeing. No `status`: whether somebody is
# on the roster is `IS_ON_THE_ROSTER`, asked of memberships.
# `updated_at` is stamped here, not carried by the caller, so no writer can put a stale value
# back. The WHERE is why it stays meaningful: `DO UPDATE` fires on every conflict whether or not
# anything differs, so without it a republish of an unchanged roster would move every person's
# `updated_at` and diff the published file for nothing.
PERSON_UPSERT = f"""
    INSERT INTO people (id, jurisdiction_ocdid, updated_at, {", ".join(_PERSON_COLUMNS)})
    VALUES (%(id)s, %(jurisdiction_ocdid)s, now(),
            {", ".join(f"%({column})s" for column in _PERSON_COLUMNS)})
    ON CONFLICT (id) DO UPDATE
       SET updated_at = now(),
           {", ".join(f"{column} = EXCLUDED.{column}" for column in _PERSON_COLUMNS)}
     WHERE ({", ".join(f"people.{column}" for column in _PERSON_COLUMNS)})
        IS DISTINCT FROM
           ({", ".join(f"EXCLUDED.{column}" for column in _PERSON_COLUMNS)})
"""


def person_upsert_params(people: list[dict]) -> list[dict]:
    """A roster's dicts as rows for `PERSON_UPSERT`.

    One caller now — `publish_changeset`. It also shaped the people files `od_sync` read back,
    until that read-back was removed.
    """
    return [
        {
            "id": person.get("id"),
            "jurisdiction_ocdid": person.get("jurisdiction_ocdid"),
            **{
                column: (person.get(column) or [])
                if column in _LIST_COLUMNS
                else person.get(column)
                for column in _PERSON_COLUMNS
            },
        }
        for person in people
    ]


def person_rows(people: Iterable[Person], jurisdiction_ocdid: str) -> list[dict]:
    return person_upsert_params(
        [
            {
                "id": person.id,
                "jurisdiction_ocdid": jurisdiction_ocdid,
                **{
                    column: list(value) if column in _LIST_COLUMNS else value
                    for column, value in person.model_dump().items()
                    if column in _PERSON_COLUMNS
                },
            }
            for person in people
        ]
    )


# withdrawn_at IS NULL, added 189: without it this found a withdrawn label assertion just as
# readily as a live one, since the ORDER BY has no opinion on withdrawal — so clearing a label
# back to derived (set_label's withdraw call) had no effect here, and the very next scrape
# would still be refused the field it was just supposed to get back.
LABEL_IS_HUMAN_SET = f"""COALESCE((
    SELECT assertions.kind = 'accept'
    FROM assertions
    WHERE assertions.entity_type = 'membership'
      AND assertions.entity_id = memberships.id
      AND assertions.field_path = '{LABEL_FIELD}'
      AND assertions.withdrawn_at IS NULL
    {LATEST_FIRST}
    LIMIT 1
), false)"""

# Only a publish that read a source advances `last_seen_at`; a hand edit still dates a new one.
_UPSERT_OPEN_MEMBERSHIPS = f"""
    INSERT INTO memberships
        (post_id, organization_id, person_id, designations, meta_unmatched_text,
         sources, start_date, end_date, first_seen_at, last_seen_at, label)
    VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s)
    ON CONFLICT (person_id, organization_id) WHERE closed_at IS NULL
    DO UPDATE SET
        last_seen_at = CASE WHEN %s
            THEN GREATEST(memberships.last_seen_at, EXCLUDED.last_seen_at)
            ELSE memberships.last_seen_at END,
        designations = EXCLUDED.designations,
        meta_unmatched_text = EXCLUDED.meta_unmatched_text,
        sources = EXCLUDED.sources,
        start_date = EXCLUDED.start_date,
        end_date = EXCLUDED.end_date,
        label = CASE WHEN {LABEL_IS_HUMAN_SET}
                     THEN memberships.label ELSE EXCLUDED.label END
"""

_DELETE_MEMBERSHIP_ROLES = "DELETE FROM membership_roles WHERE membership_id::text = %s"

_INSERT_MEMBERSHIP_ROLE = """
    INSERT INTO membership_roles (membership_id, role_id) VALUES (%s, %s)
    ON CONFLICT DO NOTHING
"""


def _upsert_params(
    binding: MembershipBinding, last_seen_at, advances_last_seen: bool
) -> tuple:
    member = binding.member
    return (
        binding.post_id,
        binding.organization_id,
        member.person_id,
        member.designations,
        member.meta_unmatched_text,
        json.dumps([source.model_dump() for source in member.sources]),
        member.start_date,
        member.end_date,
        last_seen_at,
        last_seen_at,
        member.membership_label,
        advances_last_seen,
    )


def _open_membership_key(binding: MembershipBinding) -> tuple[str, str]:
    return (binding.member.person_id, binding.organization_id)


async def upsert_open_memberships(
    cur, bindings: list[MembershipBinding], last_seen_at, advances_last_seen: bool
) -> None:
    """Open each membership, or refresh the open one; a human-set label is kept."""
    await cur.executemany(
        _UPSERT_OPEN_MEMBERSHIPS,
        [
            _upsert_params(binding, last_seen_at, advances_last_seen)
            for binding in bindings
        ],
    )


async def replace_membership_roles(
    cur, bindings: list[MembershipBinding], membership_ids: dict[tuple[str, str], str]
) -> None:
    """Replace the open memberships' extra roles (beyond the post's own) with the latest label's."""
    await cur.executemany(
        _DELETE_MEMBERSHIP_ROLES,
        [(membership_ids[_open_membership_key(binding)],) for binding in bindings],
    )
    await cur.executemany(
        _INSERT_MEMBERSHIP_ROLE,
        [
            (membership_ids[_open_membership_key(binding)], role_id)
            for binding in bindings
            for role_id in binding.member.role_ids
        ],
    )


# The stored projection as a `Roster`, the stored side of the projection diff. Read-only.
_JURISDICTIONS_WITH_A_ROSTER = """
    SELECT DISTINCT p.jurisdiction_ocdid
    FROM memberships m JOIN posts p ON p.id = m.post_id
    WHERE m.closed_at IS NULL
    ORDER BY p.jurisdiction_ocdid
"""

_STORED_PEOPLE = """
    SELECT id::text, name, other_names, phones, emails, urls, source_urls, image, cdn_image
    FROM people WHERE jurisdiction_ocdid = %s
"""

_STORED_OPEN_MEMBERSHIPS = """
    SELECT m.person_id::text, p.organization_id::text, p.role_id, p.division_ocdid, m.label
    FROM memberships m JOIN posts p ON p.id = m.post_id
    WHERE p.jurisdiction_ocdid = %s AND m.closed_at IS NULL
"""


async def jurisdictions_with_a_roster(cur) -> list[str]:
    await cur.execute(_JURISDICTIONS_WITH_A_ROSTER)
    return [row[0] for row in await cur.fetchall()]


async def stored_roster(cur, jurisdiction_ocdid: str) -> Roster:
    await cur.execute(_STORED_OPEN_MEMBERSHIPS, (jurisdiction_ocdid,))
    memberships: dict[str, list[Membership]] = {}
    for person_id, organization_id, role_id, division_ocdid, label in await cur.fetchall():
        post_id = PostKey(
            organization_id=organization_id, role_id=role_id, division_ocdid=division_ocdid
        ).post_id
        memberships.setdefault(person_id, []).append(Membership(post_id=post_id, label=label))

    await cur.execute(_STORED_PEOPLE, (jurisdiction_ocdid,))
    return Roster(
        people=tuple(
            Person(
                id=row[0],
                name=row[1],
                other_names=tuple(row[2] or ()),
                phones=tuple(row[3] or ()),
                emails=tuple(row[4] or ()),
                urls=tuple(row[5] or ()),
                source_urls=tuple(row[6] or ()),
                image=row[7],
                cdn_image=row[8],
                memberships=tuple(sorted(memberships.get(row[0], ()), key=lambda m: m.post_id)),
            )
            for row in sorted(await cur.fetchall())
        )
    )
