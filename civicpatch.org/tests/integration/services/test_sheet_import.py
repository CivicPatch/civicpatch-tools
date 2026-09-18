"""Integration tests for `services.sheet_import`.

Against the real test DB, because what is worth checking here is what a mock cannot show: that
sightings and identities land as a pair, that the changeset lands **unpublished** and waits on
the batch page, and that labels actually mint posts.

Run with:
  mise run tcp-integration

Isolation: everything is written under one sentinel jurisdiction, removed before and after each
test. `requests` cascades to `source_records`, so the rows go with it.
"""

import uuid
from typing import LiteralString
from unittest.mock import patch

import pytest
import pytest_asyncio

from core.sheet_import_rows import ImportRow, ImportStatus, Sighting
from core.membership_proposal import MembershipDisposition
from core.post_derivation import UNMATCHED_ROLE_ID
from shared.schemas import POST_FIELD
from shared.utils.statuses import ActivityType, ChangesetKind
from core.roster_diff import UNCHANGED_NOTE, ChangeCounts
from core.source_sites import SiteIndex
from lib.csv import parse_csv
from database import activity, changeset_batches, dismissals, divisions, organizations, posts
from database.database import get_pool
from database.publications import publish_attributions
from services import roster_edits
from services.batch_review import batch_review, dismiss_selected, publish_selected
from services.review_cards import with_card_data
from services.review_proposal import proposals_for_requests, review_summary_for_changeset
from services.roster import proposed_roster, proposed_roster_and_source_values
from services.sheet_import import import_rows, read_rows
from tests.integration import factories

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_sheet_test/government"
# A second town, so "one commit for the whole batch" is a claim a test can actually falsify.
_OCDID_2 = "ocd-jurisdiction/country:us/state:zz/place:zz_sheet_test_two/government"
_OCDIDS = [_OCDID, _OCDID_2]
_SHEET = "https://docs.google.com/spreadsheets/d/test/export?format=csv"
_EMAIL = "zz-sheet-import@test.civicpatch.org"


async def _cleanup():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM memberships WHERE post_id IN "
            "(SELECT id FROM posts WHERE jurisdiction_ocdid = ANY(%s))",
            (_OCDIDS,),
        )
        await cur.execute(
            "DELETE FROM posts WHERE jurisdiction_ocdid = ANY(%s)", (_OCDIDS,)
        )
        await cur.execute(
            "DELETE FROM activity WHERE jurisdiction_ocdid = ANY(%s)", (_OCDIDS,)
        )
        # Changesets first: their source records point at organizations (205: ON DELETE RESTRICT),
        # so a body cannot go while a changeset's evidence still names it.
        await cur.execute(
            "DELETE FROM changesets WHERE jurisdiction_ocdid = ANY(%s)", (_OCDIDS,)
        )
        await cur.execute(
            "DELETE FROM organizations WHERE jurisdiction_ocdid = ANY(%s)", (_OCDIDS,)
        )
        await cur.execute(
            "DELETE FROM divisions WHERE jurisdiction_ocdid = ANY(%s)", (_OCDIDS,)
        )
        await cur.execute(
            "DELETE FROM people WHERE jurisdiction_ocdid = ANY(%s)", (_OCDIDS,)
        )
        await cur.execute(
            "DELETE FROM jurisdictions WHERE jurisdiction_ocdid = ANY(%s)", (_OCDIDS,)
        )
        # By owner, not by lock key: a test that starts a second batch picks its own key, and
        # `started_by_user_id` is NOT NULL, so a missed row pins the user below.
        await cur.execute(
            "DELETE FROM changeset_batches WHERE started_by_user_id IN "
            "(SELECT id FROM users WHERE email = %s)",
            (_EMAIL,),
        )
        # Publishing can leave assertions behind, and `assertions.created_by` is NOT NULL with
        # no cascade — so the user cannot go until they do.
        await cur.execute(
            "DELETE FROM assertions WHERE created_by IN "
            "(SELECT id FROM users WHERE email = %s)",
            (_EMAIL,),
        )
        await cur.execute("DELETE FROM users WHERE email = %s", (_EMAIL,))
        await conn.commit()


@pytest_asyncio.fixture
async def user_id():
    """`requests.created_by_user_id` is a real foreign key — an import is always somebody's."""
    await _cleanup()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state) "
            "SELECT unnest(%s::text[]), 'zz'",
            (_OCDIDS,),
        )
        # Real jurisdictions get their default organization at sync time (open_data.py); this
        # raw insert bypasses that, so it has to do the pairing itself.
        await cur.execute(
            "INSERT INTO organizations (jurisdiction_ocdid, name) "
            "SELECT unnest(%s::text[]), 'Government'",
            (_OCDIDS,),
        )
        await cur.execute(
            "INSERT INTO users (email, provider, provider_user_id, username, role) "
            "VALUES (%s, 'email', %s, %s, 'maintainers') RETURNING id::text",
            (_EMAIL, _EMAIL, _EMAIL.replace("@", "-")),
        )
        row = await cur.fetchone()
        assert row is not None
        await conn.commit()
    yield row[0]
    await _cleanup()


@pytest_asyncio.fixture
async def batch_id(user_id):
    """`changesets.batch_id` is a real foreign key, so a literal string will not do."""
    return await changeset_batches.start(
        changeset_batches.BatchKind.SHEET_IMPORT,
        f"sheet:{_OCDID}",
        user_id,
        {"spreadsheet_id": "test"},
    )


def _rows(*people, ocdid: str = _OCDID) -> list[ImportRow]:
    return [
        ImportRow(
            line=0,
            jurisdiction_ocdid=ocdid,
            sighting=Sighting(name=name, label=label, source_url=_SHEET),
        )
        for name, label in people
    ]


async def _parsed(*people):
    return _rows(*people)


async def _seed_open_membership(name: str, source_labels: list[str]) -> None:
    """A currently-held post, for an import to find by name."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        person_id = str(uuid.uuid4())
        await cur.execute(
            "INSERT INTO people (id, jurisdiction_ocdid, name) VALUES (%s, %s, %s)",
            (person_id, _OCDID, name),
        )
        org = await organizations.find_or_create(cur, _OCDID)
        division = f"ocd-division/country:us/state:zz/place:zz_sheet_test"
        await divisions.find_or_create(cur, division, _OCDID)
        post_id = await posts.find_or_create(cur, _OCDID, org, "select-board-chair", division)
        await cur.execute(
            """
            INSERT INTO memberships
                (post_id, organization_id, person_id, sources, first_seen_at, last_seen_at)
            VALUES (%s, %s, %s, %s::jsonb, now(), now())
            """,
            (post_id, org, person_id, factories.sources_of(source_labels)),
        )
        await conn.commit()


async def _selected(batch_id: str, *ocdids: str) -> set[str]:
    """What a reviewer ticking these towns on the batch page would send: their changeset ids."""
    return {
        item["changeset_id"]
        for item in await changeset_batches.items(batch_id)
        if item["jurisdiction_ocdid"] in ocdids
    }


async def _published_in_sweep() -> set[str]:
    return {
        changed.jurisdiction_ocdid
        for changed in await activity.jurisdictions_changed_since(15)
        if changed.jurisdiction_ocdid in _OCDIDS
        and ActivityType.PUBLISH_REVIEW in changed.change_types
    }


async def _scalar(sql: LiteralString, params: tuple):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(sql, params)
        row = await cur.fetchone()
    assert row is not None
    return row[0]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_an_import_writes_sightings_and_waits_unpublished(user_id, batch_id):
    """The sightings are the only write — no publish. It waits on the batch page, never in the
    review pool (`test_jurisdiction_in_flight` covers that it stays out)."""
    rows = await _parsed(
        ("Ana Reyes", "Select Board Chair"), ("Bo Chen", "Select Board Member")
    )

    [result] = await import_rows(rows, user_id, batch_id)

    assert result.status is ImportStatus.IMPORTED
    assert result.people == 2
    assert result.sightings == 2

    assert (
        await _scalar(
            "SELECT count(*) FROM source_records WHERE changeset_id = %s::uuid",
            (result.changeset_id,),
        )
        == 2
    )
    # Unpublished: an import proposes a roster, it does not decide one.
    assert (
        await _scalar(
            "SELECT published_at FROM changesets WHERE id = %s::uuid", (result.changeset_id,)
        )
        is None
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_every_sighting_gets_an_identity(user_id, batch_id):
    """Linkage is written with the evidence, in one transaction — a record with no identity
    would be evidence nothing can find."""
    rows = await _parsed(("Ana Reyes", "Select Board Chair"))

    [result] = await import_rows(rows, user_id, batch_id)

    assert (
        await _scalar(
            """
            SELECT count(*) FROM source_records sr
            JOIN source_record_identities i ON i.source_record_id = sr.id
            WHERE sr.changeset_id = %s::uuid
            """,
            (result.changeset_id,),
        )
        == 1
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_label_mints_the_post_it_implies(user_id, batch_id):
    """The sheet carries no post id, so the label is the only thing that can imply a seat — and
    projecting it is what makes the 194 MA jurisdictions with no posts importable at all.

    Projected, not created: an import proposes seats like any other changeset, and publishing is
    what mints them. So the count is reported and the table stays empty."""
    rows = await _parsed(("Ana Reyes", "Select Board Chair"))

    [result] = await import_rows(rows, user_id, batch_id)

    assert result.posts >= 1
    assert (
        await _scalar(
            "SELECT count(*) FROM posts WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        == 0
    ), "ingest minted a seat; only publishing should"


async def _published(name: str) -> tuple[str, str]:
    """The seeded person's id and the post they hold."""
    person_id = await _scalar(
        "SELECT id::text FROM people WHERE jurisdiction_ocdid = %s AND name = %s", (_OCDID, name)
    )
    post_id = await _scalar(
        "SELECT post_id::text FROM memberships WHERE person_id = %s::uuid AND closed_at IS NULL",
        (person_id,),
    )
    return person_id, post_id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_blank_label_keeps_the_current_post(user_id, batch_id):
    """What `inherit` was for, without the word: a blank label states no post, so the person
    keeps the one they hold — not one re-derived from label text, which moved people."""
    await _seed_open_membership("Ana Reyes", ["Select Board Chair"])
    person_id, post_id = await _published("Ana Reyes")

    [result] = await import_rows(_rows(("Ana Reyes", "")), user_id, batch_id)
    assert result.changeset_id is not None
    [ana] = await proposed_roster(result.changeset_id, _OCDID)
    changes = (await proposals_for_requests([result.changeset_id]))[result.changeset_id]

    assert ana["id"] == person_id
    assert ana[POST_FIELD] == post_id
    assert [change.disposition for change in changes] == [MembershipDisposition.UNCHANGED]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_each_row_is_noted_with_what_it_changes(user_id, batch_id):
    """Keyed by the row's name, so write-back can find it again after a re-read."""
    await _seed_open_membership("Ana Reyes", ["Select Board Chair"])

    [result] = await import_rows(
        _rows(("Ana Reyes", ""), ("Bo Chen", "Town Clerk")), user_id, batch_id
    )

    assert result.notes["ana reyes"] == UNCHANGED_NOTE
    assert result.notes["bo chen"].startswith("new person; new post: ")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_town_whose_latest_import_was_dismissed_is_found(user_id, batch_id):
    rows = _rows(("Ana Reyes", "Select Board Chair")) + _rows(
        ("Bo Nunez", "Town Clerk"), ocdid=_OCDID_2
    )
    await import_rows(rows, user_id, batch_id)

    await dismiss_selected(batch_id, await _selected(batch_id, _OCDID), user_id)

    assert await dismissals.latest_import_dismissed(_OCDIDS) == {_OCDID}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_blank_cell_keeps_the_published_value(user_id, batch_id):
    """The sheet has no links column and this row has no email: neither is a removal."""
    await _seed_open_membership("Ana Reyes", ["Select Board Chair"])
    person_id, _ = await _published("Ana Reyes")
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE people SET emails = %s, urls = %s WHERE id = %s::uuid",
            (["ana@town.gov"], ["https://town.gov/ana"], person_id),
        )
        await conn.commit()

    [result] = await import_rows(_rows(("Ana Reyes", "Select Board Chair")), user_id, batch_id)
    assert result.changeset_id is not None
    [ana] = await proposed_roster(result.changeset_id, _OCDID)

    assert ana["emails"] == ["ana@town.gov"]
    assert ana["urls"] == ["https://town.gov/ana"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sightings_belong_to_the_default_organization(user_id, batch_id):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        default = await organizations.get_default(cur, _OCDID)
        await organizations.find_or_create(cur, _OCDID, "School Board")
        await conn.commit()

    [result] = await import_rows(_rows(("Ana Reyes", "Select Board Chair")), user_id, batch_id)

    assert await _scalar(
        "SELECT array_agg(DISTINCT organization_id::text) FROM source_records WHERE changeset_id = %s",
        (result.changeset_id,),
    ) == [default]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_someone_new_with_no_label_is_unmatched(user_id, batch_id):
    """Nothing published to keep, so a blank label derives to the unmatched role — publishable,
    for a reviewer to place later."""
    [result] = await import_rows(_rows(("Nobody Yet", "")), user_id, batch_id)
    assert result.changeset_id is not None
    changes = (await proposals_for_requests([result.changeset_id]))[result.changeset_id]

    assert [(change.disposition, change.post.role_id) for change in changes] == [
        (MembershipDisposition.NEW, UNMATCHED_ROLE_ID)
    ]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_the_batch_is_recorded_on_the_request(user_id, batch_id):
    """So a card can name the import that raised it, and the bulk review screen can ask
    `requests` for this batch's *current* state rather than reading a run-time snapshot."""
    rows = await _parsed(("Ana Reyes", "Select Board Chair"))

    [result] = await import_rows(rows, user_id, batch_id)

    assert (
        await _scalar(
            "SELECT batch_id::text FROM changesets WHERE id = %s::uuid",
            (result.changeset_id,),
        )
        == batch_id
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_one_jurisdiction_failing_does_not_cost_the_others(user_id, batch_id):
    """Jurisdictions are independent — own request, own sightings. An unknown ocdid violates
    the requests foreign key, and the good one must still import."""
    good = _rows(("Ana Reyes", "Select Board Chair"))
    missing = "ocd-jurisdiction/country:us/state:zz/place:zz_not_registered/government"
    bad = _rows(("Cy Diaz", "Chair"), ocdid=missing)

    results = await import_rows(good + bad, user_id, batch_id)
    by_ocdid = {result.jurisdiction_ocdid: result for result in results}

    assert by_ocdid[_OCDID].status is ImportStatus.IMPORTED
    assert by_ocdid[missing].status is ImportStatus.FAILED
    assert by_ocdid[missing].error


@pytest.mark.integration
@pytest.mark.asyncio
async def test_end_to_end_from_csv_text(user_id, batch_id):
    """The whole chain a volunteer's sheet actually takes: two tabs of CSV in, a review card out.

    Deliberately includes what a real sheet carries — a header a human typed in mixed case, a
    quoted comma in a name, and a row missing its name. That bad row is in its own jurisdiction,
    not `_OCDID`'s — "blocked whole, never partly" would otherwise take the two good rows down
    with it, which is `test_sheet_read.py`'s claim, not this one's.
    """
    roster_csv = (
        "Jurisdiction_OCDID,name,source_url,label,email\n"
        f'{_OCDID},"Reyes, Ana",https://zz.gov/roster,Select Board Chair,ana@zz.gov\n'
        f"{_OCDID},Bo Chen,https://zz.gov/roster,Select Board Member,bo@zz.gov\n"
        f"{_OCDID_2},,https://zz.gov/roster,Select Board Clerk,cy@zz.gov\n"
    )
    read = read_rows(parse_csv(roster_csv), SiteIndex())

    # The name-less row is rejected, and takes nobody else with it.
    assert [(error.line, error.column) for error in read.preview.errors] == [
        (4, "name")
    ]
    assert len(read.rows) == 2

    [result] = await import_rows(read.rows, user_id, batch_id)

    assert result.status is ImportStatus.IMPORTED
    assert result.people == 2
    assert result.posts >= 1
    # A quoted comma survives the whole way to the sighting.
    assert (
        await _scalar(
            "SELECT count(*) FROM source_records WHERE changeset_id = %s::uuid AND name = %s",
            (result.changeset_id, "Reyes, Ana"),
        )
        == 1
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_the_batch_review_shows_the_towns_it_made(user_id, batch_id):
    """One pass over what the run produced, counting people from the sightings."""
    rows = await _parsed(
        ("Ana Reyes", "Select Board Chair"), ("Bo Chen", "Select Board Member")
    )
    await import_rows(rows, user_id, batch_id)

    review = await batch_review(batch_id)

    assert review is not None
    [jurisdiction] = review.jurisdictions
    assert jurisdiction.jurisdiction_ocdid == _OCDID
    assert jurisdiction.changeset_state == "open"
    assert jurisdiction.people == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_the_batch_review_counts_what_each_town_changes(user_id, batch_id):
    """Nothing is published here yet, so both people are added."""
    rows = await _parsed(
        ("Ana Reyes", "Select Board Chair"), ("Bo Chen", "Select Board Member")
    )
    await import_rows(rows, user_id, batch_id)

    review = await batch_review(batch_id)

    assert review is not None
    [jurisdiction] = review.jurisdictions
    assert jurisdiction.change_counts == ChangeCounts(added_people=2)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_batched_card_says_what_the_single_card_reads_say(user_id, batch_id):
    """The batch loader and the per-card endpoints must not disagree about one changeset."""
    rows = await _parsed(("Ana Reyes", "Select Board Chair"))
    [result] = await import_rows(rows, user_id, batch_id)
    assert result.changeset_id is not None
    [card] = await with_card_data([result.changeset_id])

    _, overridden = await proposed_roster_and_source_values(result.changeset_id, _OCDID)
    assert card.jurisdiction_ocdid == _OCDID
    assert card.review == await review_summary_for_changeset(result.changeset_id)
    assert card.overridden_source_values == overridden
    assert card.organizations == await posts.list_by_organization(_OCDID)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_an_unknown_batch_reviews_as_nothing(user_id):
    assert await batch_review("00000000-0000-4000-8000-00000000dead") is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_publishing_a_selection_leaves_the_rest_open(user_id, batch_id):
    """The page is a view, not a queue: publishing some does not make the others disappear."""
    rows = await _parsed(("Ana Reyes", "Select Board Chair"))
    await import_rows(rows, user_id, batch_id)

    [result] = await publish_selected(batch_id, await _selected(batch_id, _OCDID), user_id)
    assert result.published is True

    review = await batch_review(batch_id)
    assert review is not None
    [jurisdiction] = review.jurisdictions
    assert jurisdiction.changeset_state == "published"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dismissing_a_selection_rejects_it_and_leaves_the_rest_open(
    user_id, batch_id
):
    rows = _rows(("Ana Reyes", "Select Board Chair")) + _rows(
        ("Bo Nunez", "Town Clerk"), ocdid=_OCDID_2
    )
    await import_rows(rows, user_id, batch_id)

    picked = await _selected(batch_id, _OCDID)
    assert await dismiss_selected(batch_id, picked, user_id) == list(picked)

    review = await batch_review(batch_id)
    assert review is not None
    states = {j.jurisdiction_ocdid: j.changeset_state for j in review.jurisdictions}
    assert states == {_OCDID: "dismissed", _OCDID_2: "open"}
    assert (
        await _scalar(
            "SELECT dismissed_reason FROM changesets WHERE batch_id = %s::uuid "
            "AND jurisdiction_ocdid = %s",
            (batch_id, _OCDID),
        )
        == "rejected"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_published_town_is_not_dismissed(user_id, batch_id):
    rows = await _parsed(("Ana Reyes", "Select Board Chair"))
    await import_rows(rows, user_id, batch_id)
    await publish_selected(batch_id, await _selected(batch_id, _OCDID), user_id)

    assert await dismiss_selected(batch_id, await _selected(batch_id, _OCDID), user_id) == []

    review = await batch_review(batch_id)
    assert review is not None
    assert review.jurisdictions[0].changeset_state == "published"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_town_nobody_selected_is_left_alone(user_id, batch_id):
    rows = await _parsed(("Ana Reyes", "Select Board Chair"))
    await import_rows(rows, user_id, batch_id)

    assert await publish_selected(batch_id, set(), user_id) == []

    review = await batch_review(batch_id)
    assert review is not None
    assert review.jurisdictions[0].changeset_state == "open"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_publishing_twice_does_not_republish(user_id, batch_id):
    """A town already live — published here or from the ordinary queue — is skipped rather than
    superseding itself for nothing."""
    rows = await _parsed(("Ana Reyes", "Select Board Chair"))
    await import_rows(rows, user_id, batch_id)
    await publish_selected(batch_id, await _selected(batch_id, _OCDID), user_id)

    assert await publish_selected(batch_id, await _selected(batch_id, _OCDID), user_id) == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_publishing_two_towns_reaches_the_open_data_sweep(user_id, batch_id):
    """Nothing is queued at publish: the 5-minute sweep reads the activity feed, so a batch
    publish reaches open-data only if each town is in that feed as a publish."""
    rows = _rows(("Ana Reyes", "Select Board Chair")) + _rows(
        ("Bo Nunez", "Town Clerk"), ocdid=_OCDID_2
    )
    await import_rows(rows, user_id, batch_id)

    results = await publish_selected(batch_id, await _selected(batch_id, *_OCDIDS), user_id)
    assert [result.published for result in results] == [True, True]

    assert await _published_in_sweep() == set(_OCDIDS)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_town_that_refused_to_publish_stays_out_of_the_sweep(user_id, batch_id):
    """One jurisdiction failing must not keep the others out of open-data, and must not put
    itself in — the sweep covers what reached the database, not what was selected."""
    rows = _rows(("Ana Reyes", "Select Board Chair")) + _rows(
        ("Bo Nunez", "Town Clerk"), ocdid=_OCDID_2
    )
    await import_rows(rows, user_id, batch_id)

    real_publish = roster_edits.publish
    refused = []

    async def refuse_the_first(*args):
        if not refused:
            refused.append(args[1])
            raise RuntimeError("supersede guard")
        return await real_publish(*args)

    with patch("services.batch_review.roster_edits.publish", side_effect=refuse_the_first):
        results = await publish_selected(batch_id, await _selected(batch_id, *_OCDIDS), user_id)

    assert sorted(result.published for result in results) == [False, True]
    assert await _published_in_sweep() == set(_OCDIDS) - set(refused)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_the_open_data_commit_names_who_published_the_import(user_id, batch_id):
    """Only the published town is attributed; the open one is in the sweep's feed too, via its
    `sheet_import` row, but nobody has published it."""
    rows = _rows(("Ana Reyes", "Select Board Chair")) + _rows(
        ("Bo Nunez", "Town Clerk"), ocdid=_OCDID_2
    )
    await import_rows(rows, user_id, batch_id)
    published_id, open_id = [
        next(iter(await _selected(batch_id, ocdid))) for ocdid in _OCDIDS
    ]
    await publish_selected(batch_id, {published_id}, user_id)

    attributions = await publish_attributions([published_id, open_id])

    assert list(attributions) == [published_id]
    attribution = attributions[published_id]
    assert attribution.kind is ChangesetKind.SHEET_IMPORT
    assert attribution.published_by == _EMAIL.replace("@", "-")
    assert attribution.batch_id == batch_id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_the_running_import_is_findable_without_being_remembered(
    user_id, batch_id
):
    """Whoever opens the page finds the import under way — there is one spreadsheet and one
    lock, so it is a fact about the system, not about the browser that started it."""
    found = await changeset_batches.latest(changeset_batches.BatchKind.SHEET_IMPORT)

    assert found is not None
    assert found["id"] == batch_id
    assert found["status"] == changeset_batches.BatchStatus.RUNNING


@pytest.mark.integration
@pytest.mark.asyncio
async def test_publishing_dismisses_the_cards_it_makes_pointless(user_id, batch_id):
    """Two imports minutes apart leave two cards for one locality. Publishing the newer one
    makes the older obviously stale, and it used to sit in the queue until a timed sweep
    noticed — offering a reviewer a card that could only ever refuse."""
    rows = await _parsed(("Ana Reyes", "Select Board Chair"))
    await import_rows(rows, user_id, batch_id)
    older = await _scalar(
        "SELECT id::text FROM changesets WHERE jurisdiction_ocdid = %s", (_OCDID,)
    )

    # A second import of the same locality, which is what a re-run produces.
    second = await changeset_batches.start(
        changeset_batches.BatchKind.SHEET_IMPORT,
        f"sheet:{_OCDID}:again",
        user_id,
        {"spreadsheet_id": "test"},
    )
    await import_rows(await _parsed(("Bo Nunez", "Town Clerk")), user_id, second)

    [result] = await publish_selected(second, await _selected(second, _OCDID), user_id)
    assert result.published is True

    assert (
        await _scalar(
            "SELECT dismissed_reason FROM changesets WHERE id = %s", (older,)
        )
        == "superseded"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_one_sheet_cannot_have_two_imports_at_once(user_id, batch_id):
    """Enforced by a partial unique index, not by application code checking first — a
    check-then-insert has a window two callers can both pass through.

    Two runs over one sheet would each raise a review card per locality, which is how a single
    import turns into duplicate cards nobody can tell apart.
    """
    with pytest.raises(changeset_batches.BatchAlreadyRunning):
        await changeset_batches.start(
            changeset_batches.BatchKind.SHEET_IMPORT,
            f"sheet:{_OCDID}",
            user_id,
            {"spreadsheet_id": "test"},
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_the_lock_lifts_when_the_batch_finishes(user_id, batch_id):
    """The index is partial on `finished_at IS NULL`, and `run_import` stamps it on success and
    failure alike — so the sheet frees itself for the next run either way."""
    await changeset_batches.finish(batch_id, changeset_batches.BatchStatus.SUCCEEDED)

    again = await changeset_batches.start(
        changeset_batches.BatchKind.SHEET_IMPORT,
        f"sheet:{_OCDID}",
        user_id,
        {"spreadsheet_id": "test"},
    )
    assert again != batch_id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_locality_the_sheet_says_is_handled_raises_no_second_card(
    user_id, batch_id
):
    """Re-reading a sheet nobody has touched should do nothing. It used to raise a duplicate
    card per locality per run and lean on supersede to tidy up: six runs on dev left Centralia
    with five cards, four swept and one published."""
    rows = _rows(("Ana Reyes", "Select Board Chair"))
    for row in rows:
        row.status = ImportStatus.IMPORTED

    results = await import_rows(rows, user_id, batch_id)

    assert [result.status for result in results] == [ImportStatus.UNCHANGED]
    assert results[0].changeset_id is None
    assert (
        await _scalar(
            "SELECT count(*) FROM changesets WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        == 0
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_clearing_one_row_brings_the_whole_roster_back(user_id, batch_id):
    """Whole, not just the cleared row: a card carrying one of two people would propose closing
    the other's membership when published."""
    rows = _rows(("Ana Reyes", "Select Board Chair"), ("Bo Chen", "Town Clerk"))
    rows[0].status = ImportStatus.IMPORTED
    rows[1].status = ""

    [result] = await import_rows(rows, user_id, batch_id)

    assert result.status is ImportStatus.IMPORTED
    assert (
        await _scalar(
            "SELECT count(*) FROM source_records WHERE changeset_id = %s::uuid",
            (result.changeset_id,),
        )
        == 2
    )


async def _age_batch(batch_id: str, interval: str) -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"UPDATE changeset_batches SET started_at = now() - interval '{interval}' "
            "WHERE id::text = %s",
            (batch_id,),
        )
        await conn.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_second_import_of_the_same_sheet_is_refused(user_id):
    """The lock doing its job: two runs over one sheet would double every request."""
    lock_key = f"sheet:{_OCDID}:refused"
    await changeset_batches.start(
        changeset_batches.BatchKind.SHEET_IMPORT, lock_key, user_id, {}
    )

    with pytest.raises(changeset_batches.BatchAlreadyRunning):
        await changeset_batches.start(
            changeset_batches.BatchKind.SHEET_IMPORT, lock_key, user_id, {}
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_batch_whose_process_died_does_not_wedge_the_sheet_forever(user_id):
    """`finish` releases the lock on every path the code takes, but a killed worker takes none
    of them, and the partial unique index is on `finished_at IS NULL`. Before this, one restart
    mid-import held that sheet against every future import until somebody ran an UPDATE by hand.
    """
    lock_key = f"sheet:{_OCDID}:abandoned"
    abandoned = await changeset_batches.start(
        changeset_batches.BatchKind.SHEET_IMPORT, lock_key, user_id, {}
    )
    await _age_batch(abandoned, "3 hours")

    taken_over = await changeset_batches.start(
        changeset_batches.BatchKind.SHEET_IMPORT, lock_key, user_id, {}
    )

    assert taken_over != abandoned
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT status, error, finished_at IS NOT NULL FROM changeset_batches "
            "WHERE id::text = %s",
            (abandoned,),
        )
        status, error, finished = await cur.fetchone()
    assert (status, finished) == (changeset_batches.BatchStatus.FAILED.value, True)
    # Says why, because the batch page shows it and "failed" with no reason reads as a bug in
    # the import rather than a process that went away.
    assert "abandoned" in error


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_slow_import_still_holds_its_lock(user_id):
    """The takeover is time-bound, not unconditional: a long import is not an abandoned one."""
    lock_key = f"sheet:{_OCDID}:slow"
    running = await changeset_batches.start(
        changeset_batches.BatchKind.SHEET_IMPORT, lock_key, user_id, {}
    )
    await _age_batch(running, "20 minutes")

    with pytest.raises(changeset_batches.BatchAlreadyRunning):
        await changeset_batches.start(
            changeset_batches.BatchKind.SHEET_IMPORT, lock_key, user_id, {}
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_abandoned_batch_on_another_sheet_is_left_alone(user_id):
    """Per key: releasing every stale batch would rewrite history for sheets nobody is importing."""
    other = await changeset_batches.start(
        changeset_batches.BatchKind.SHEET_IMPORT, f"sheet:{_OCDID}:other", user_id, {}
    )
    await _age_batch(other, "3 hours")

    await changeset_batches.start(
        changeset_batches.BatchKind.SHEET_IMPORT, f"sheet:{_OCDID}:mine", user_id, {}
    )

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT finished_at IS NULL FROM changeset_batches WHERE id::text = %s", (other,)
        )
        still_open = (await cur.fetchone())[0]
    assert still_open is True
