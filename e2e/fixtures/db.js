import crypto from "node:crypto";
import pg from "pg";

const { Client } = pg;

// Divisions for the fixture people. Real records always carry one —
// resolve_division is typed `-> str` and always returns a division, and a count
// over production found 0 blank of 19,790 — so a fixture with null models a
// state the pipeline cannot produce. It also blocks publishing, since division
// is required, which is how this was noticed.
const RECONCILE_DIVISION =
  "ocd-division/country:us/state:nh/place:e2e_reconcile";
const MARKERS_DIVISION = "ocd-division/country:us/state:me/place:e2e_markers";

// Fixed IDs so teardown can target them precisely
const TEST_USER_PROVIDER = "github";
const TEST_USER_PROVIDER_ID = "test-user-e2e";
export const TEST_JURISDICTION_OCDID =
  "ocd-jurisdiction/country:us/state:nj/place:e2e_test/government";
export const TEST_REQUEST_ID = "00000000-0000-0000-eeee-000000000001";
// person_id is a uuid since migration 144 — the old "e2e-jane" style fails at the insert now.
export const JANE_PERSON_ID = "00000000-0000-0000-aaaa-000000000001";

/** A deterministic person uuid per request, so teardown and assertions can both find it. */
function personIdFor(requestId) {
  return "00000000-0000-0000-aaaa-" + requestId.slice(-12);
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * Fixture people are named by readable slugs — "recon-maria", "dup-shared" — but
 * `source_record_identities.person_id` became a uuid in migration 144, so the slug can no
 * longer be inserted. Hashing keeps the fixtures readable and stable: the same slug always
 * yields the same id, which is what lets two sightings deliberately share a person.
 */
function personUuid(slug) {
  if (UUID.test(slug)) return slug;
  const hex = crypto.createHash("md5").update(slug).digest("hex");
  return [
    hex.slice(0, 8),
    hex.slice(8, 12),
    hex.slice(12, 16),
    hex.slice(16, 20),
    hex.slice(20, 32),
  ].join("-");
}

// issue_key for the seeded unrecognized_role issue. It is the role name itself —
// see upsert_issue in database/issues.py, which keys this issue type on the role.
export const UNRECOGNIZED_ROLE_KEY = "Deputy Vice Chair (e2e)";
const TEST_PR_ID = "00000000-0000-0000-eeee-000000000002";

export const TEST_JURISDICTION_OCDID_2 =
  "ocd-jurisdiction/country:us/state:nj/place:e2e_test_2/government";
export const TEST_REQUEST_ID_2 = "00000000-0000-0000-eeee-000000000003";
const TEST_PR_ID_2 = "00000000-0000-0000-eeee-000000000004";

export const TEST_JURISDICTION_OCDID_3 =
  "ocd-jurisdiction/country:us/state:nj/place:e2e_test_3/government";
export const TEST_REQUEST_ID_3 = "00000000-0000-0000-eeee-000000000005";
const TEST_PR_ID_3 = "00000000-0000-0000-eeee-000000000006";

// Baseline fixture — a first-capture jurisdiction (scraped_at left NULL) so the
// review renders in BASELINE mode (banner, no diff panel). The baseline-mode spec
// deep-links to it by request_id. Kept in its own state (vt) so this extra open
// card doesn't pollute the nj review queue the state-switching specs count on.
export const BASELINE_JURISDICTION_OCDID =
  "ocd-jurisdiction/country:us/state:vt/place:e2e_baseline/government";
export const BASELINE_REQUEST_ID = "00000000-0000-0000-eeee-000000000007";
const BASELINE_PR_ID = "00000000-0000-0000-eeee-000000000008";
const BASELINE_PR_NUMBER = 4;

// Populated reconcile fixture — a previously-scraped jurisdiction (scraped_at
// set) with existing people, so the diff renders real changed/added/removed
// states. Own state (vt2 → "nh") and deep-linked by request_id, like baseline.
export const RECONCILE_JURISDICTION_OCDID =
  "ocd-jurisdiction/country:us/state:nh/place:e2e_reconcile/government";
export const RECONCILE_REQUEST_ID = "00000000-0000-0000-eeee-000000000009";
const RECONCILE_PR_ID = "00000000-0000-0000-eeee-00000000000a";
const RECONCILE_PR_NUMBER = 5;

// Scale fixture — a realistically-sized council (§20). Every other card here has
// two or three people, which makes the layout questions the redesign exists to
// answer unfalsifiable: whether the collapse rule earns its keep, whether the
// editor becomes an unusable scroll, whether the grid holds at density. Own state
// (ma) so this large open card stays out of every other spec's review queue.
export const SCALE_JURISDICTION_OCDID =
  "ocd-jurisdiction/country:us/state:ma/place:e2e_scale/government";
export const SCALE_REQUEST_ID = "00000000-0000-0000-eeee-00000000000f";
const SCALE_PR_ID = "00000000-0000-0000-eeee-000000000010";
const SCALE_PR_NUMBER = 8;

const SCALE_DIVISION_BASE = "ocd-division/country:us/state:ma/place:e2e_scale";

// Built rather than written out: 40 near-identical records would bury the four
// facts that matter (who changed, who is new, who was dropped, who is untouched)
// in a wall of literals.
function scalePerson(index, overrides = {}) {
  const n = String(index).padStart(2, "0");
  return {
    id: `scale-p${n}`,
    name: `Councillor ${n} Scale`,
    office: {
      name: "Council Member",
      division_ocdid: `${SCALE_DIVISION_BASE}/ward:${index}`,
    },
    emails: [`ward${index}@scale.gov`],
    phones: [`(555) 020-01${n}`],
    urls: [`https://scale.gov/ward/${index}`],
    other_names: [],
    source_urls: ["https://scale.gov/council"],
    start_date: "2023",
    end_date: "2027",
    ...overrides,
  };
}

const SCALE_EXISTING_COUNT = 38;
const SCALE_DROPPED = [36, 37, 38]; // in the DB, absent from this scrape
const SCALE_CHANGED = [2, 5, 9, 13, 18, 21, 26, 30, 33, 35];

function buildScaleExisting() {
  return Array.from({ length: SCALE_EXISTING_COUNT }, (_, i) =>
    scalePerson(i + 1, { cdn_image: `https://cdn.test/scale-${i + 1}.jpg` }),
  );
}

function buildScaleProposed() {
  const carried = [];
  for (let i = 1; i <= SCALE_EXISTING_COUNT; i++) {
    if (SCALE_DROPPED.includes(i)) continue;
    // A spread of change shapes, so the collapse rule has something to collapse:
    // most people are untouched, and the ones that moved moved differently.
    const changed = SCALE_CHANGED.includes(i);
    carried.push(
      scalePerson(i, {
        image: `https://scale.gov/photo/${i}.jpg`,
        ...(changed && i % 3 === 0
          ? {
              office: {
                name: "Council President",
                division_ocdid: `${SCALE_DIVISION_BASE}/ward:${i}`,
              },
            }
          : {}),
        ...(changed && i % 3 === 1
          ? { emails: [`ward${i}@scale.gov`, `c${i}@scale.gov`] }
          : {}),
        ...(changed && i % 3 === 2 ? { end_date: "2029", phones: [] } : {}),
      }),
    );
  }
  const added = Array.from({ length: 5 }, (_, i) => {
    const n = String(i + 1).padStart(2, "0");
    return {
      id: `scale-n${n}`,
      name: `Newcomer ${n} Scale`,
      office: {
        name: "Council Member",
        division_ocdid: `${SCALE_DIVISION_BASE}/ward:${39 + i}`,
      },
      emails: [`new${i + 1}@scale.gov`],
      phones: [],
      urls: [],
      other_names: [],
      source_urls: ["https://scale.gov/council"],
    };
  });
  return [...carried, ...added];
}

// Duplicate-id fixture (§21.8) — two proposed people resolving to one id, which
// is what merge manufactures: matching consults aliases, so the next scrape
// resolves both entries of a merged pair to the survivor. Own state (nm).
export const DUPLICATE_JURISDICTION_OCDID =
  "ocd-jurisdiction/country:us/state:nm/place:e2e_duplicate/government";
export const DUPLICATE_REQUEST_ID = "00000000-0000-0000-eeee-000000000016";
const DUPLICATE_PR_ID = "00000000-0000-0000-eeee-000000000017";
const DUPLICATE_PR_NUMBER = 16;

// TX fixture — minimal data so cross-state isolation tests can positively
// assert TX content (not just the absence of NJ content).
export const TX_JURISDICTION_OCDID =
  "ocd-jurisdiction/country:us/state:tx/place:e2e_tx/government";
export const TX_REQUEST_ID = "00000000-0000-0000-eeee-000000000010";
const TX_PR_ID = "00000000-0000-0000-eeee-000000000011";

// Issue-markers fixture — reconcile mode (scraped_at set), no existing people so
// every proposed person renders as an "added" card. Its issues carry
// structured issues that anchor to proposed person ids, exercising the review card's
// per-card markers. Own state (me) and deep-linked by request_id, like the others.
export const MARKERS_JURISDICTION_OCDID =
  "ocd-jurisdiction/country:us/state:me/place:e2e_markers/government";
export const MARKERS_REQUEST_ID = "00000000-0000-0000-eeee-000000000012";
const MARKERS_PR_ID = "00000000-0000-0000-eeee-000000000013";
const MARKERS_PR_NUMBER = 12;

// Read-only fixture — a published request, the state a card lands in once it has
// been published. It is the only fixture with published_at set, so the only one that
// renders the terminal-status banner, the open-data link and the jurisdiction website
// link, and that hides the publish/save/close actions. Its request is still
// 'merged' because the card's link still reads PR metadata.
// Own state (ri) and deep-linked by request_id: a published request is out of the
// review pool, so it is only reachable by link, which is how reviewers reach it too.
export const READ_ONLY_JURISDICTION_OCDID =
  "ocd-jurisdiction/country:us/state:ri/place:e2e_read_only/government";
export const READ_ONLY_REQUEST_ID = "00000000-0000-0000-eeee-000000000014";
export const READ_ONLY_PR_URL =
  "https://github.com/civicpatch/open-data/pull/14";
export const READ_ONLY_WEBSITE_URL = "https://e2e-readonly.example.gov";
const READ_ONLY_PR_ID = "00000000-0000-0000-eeee-000000000015";
const READ_ONLY_PR_NUMBER = 14;

// Map fixtures — one jurisdiction per status bucket so map e2e tests can assert
// fresh/stale/gap/untracked colors deterministically against known OCD IDs.
export const MAP_FIXTURES = {
  fresh: "ocd-jurisdiction/country:us/state:nj/place:e2e_map_fresh/government",
  stale: "ocd-jurisdiction/country:us/state:nj/place:e2e_map_stale/government",
  gap: "ocd-jurisdiction/country:us/state:nj/place:e2e_map_gap/government",
  untracked:
    "ocd-jurisdiction/country:us/state:nj/place:e2e_map_untracked/government",
};

function makeClient() {
  return new Client({
    connectionString:
      process.env.E2E_DB_URL ??
      "postgres://e2e:e2e_password@localhost:8101/e2e_db",
  });
}

// Every state any fixture uses, seeded as a level='state' jurisdiction.
//
// Not decoration: /api/v1/jurisdictions/states is built from these rows, and the state
// selector treats a stored state that is missing from that list as invalid and *clears* it
// (select-state.js). With no state rows the fixtures' `app:default-state` was wiped on load,
// the review page fell back to "Pick a state to begin", and every card-dependent spec timed
// out waiting for a start button that never rendered.
const STATE_JURISDICTIONS = [
  ["ma", "Massachusetts"],
  ["me", "Maine"],
  ["nh", "New Hampshire"],
  ["nj", "New Jersey"],
  ["nm", "New Mexico"],
  ["ri", "Rhode Island"],
  ["tx", "Texas"],
  ["vt", "Vermont"],
];

const stateOcdid = (code) => `ocd-jurisdiction/country:us/state:${code}/government`;

/**
 * The fixtures describe people as the old `data_json` did — name, office, contact lists. A
 * sighting is flatter and singular, which is what `source_records` stores.
 */
function asSightings(proposed) {
  return proposed.map(function (person) {
    return {
      person_id: person.id,
      name: person.name,
      label: person.office?.name ?? "",
      email: person.emails?.[0] ?? null,
      phone: person.phones?.[0] ?? null,
      url: person.urls?.[0] ?? null,
      image: person.image ?? null,
      start_date: person.start_date ?? null,
      end_date: person.end_date ?? null,
    };
  });
}

/**
 * A review card as the current schema models one.
 *
 * `AVAILABLE_FOR_REVIEW` is `EXISTS (source_records for this request)`, so the sightings are
 * what put a card in the pool — the open `pull_requests` row that used to do it went with
 * migration 141, and `requests.data_json` with 142. The roster a reviewer sees is derived from
 * these sightings, not stored.
 */
async function seedReviewCard(
  client,
  { requestId, ocdid, people = [], publishedAt = null },
) {
  await client.query(
    `INSERT INTO requests (id, request_type, jurisdiction_ocdid, arguments_json,
                           status, progress, sourced_at, created_at, published_at)
     VALUES ($1, 'people_collection', $2, '{}', 'success', 100, NOW(), NOW(), $3)
     ON CONFLICT (id) DO NOTHING`,
    [requestId, ocdid, publishedAt],
  );
  // Re-seeding must not double the sightings: source_records has an auto id, so there is
  // nothing to ON CONFLICT on.
  await client.query(`DELETE FROM source_records WHERE request_id = $1`, [
    requestId,
  ]);
  for (const person of people) {
    const { rows } = await client.query(
      `INSERT INTO source_records (request_id, jurisdiction_ocdid, name, label, source_url,
                                   url, phone, email, image, start_date, end_date)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
       RETURNING id`,
      [
        requestId,
        ocdid,
        person.name,
        person.label ?? "",
        person.source_url ?? "https://example.gov/roster",
        person.url ?? null,
        person.phone ?? null,
        person.email ?? null,
        person.image ?? null,
        person.start_date ?? null,
        person.end_date ?? null,
      ],
    );
    await client.query(
      `INSERT INTO source_record_identities (source_record_id, person_id, resolved_at)
       VALUES ($1, $2, NOW())`,
      [rows[0].id, personUuid(person.person_id)],
    );
  }
}

/** A published person. `people.data` and `people.status` are gone — these are real columns now,
 *  and whether somebody is seated is a memberships question. */
async function seedPerson(client, ocdid, person) {
  await client.query(
    `INSERT INTO people (id, jurisdiction_ocdid, name, other_names, phones, emails,
                         urls, source_urls, image, cdn_image, updated_at)
     VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,NOW())
     ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name`,
    [
      // Same slug-to-uuid mapping as the sightings, so an existing person and a sighting that
      // proposes a change to them resolve to the same id.
      personUuid(person.id),
      ocdid,
      person.name,
      person.other_names ?? [],
      person.phones ?? [],
      person.emails ?? [],
      person.urls ?? [],
      person.source_urls ?? [],
      person.image ?? null,
      person.cdn_image ?? null,
    ],
  );
}

export async function seedE2eFixtures() {
  const client = makeClient();
  await client.connect();
  try {
    for (const [code, name] of STATE_JURISDICTIONS) {
      await client.query(
        `INSERT INTO jurisdictions (jurisdiction_ocdid, state, level, status, data)
         VALUES ($1, $2, 'state', 'active', $3)
         ON CONFLICT (jurisdiction_ocdid) DO UPDATE SET data = EXCLUDED.data`,
        [stateOcdid(code), code, JSON.stringify({ name })],
      );
    }

    // User. Seeded at the `contributors` level so the existing review-session
    // and PR-merge e2e tests still work — those write routes were bumped to
    // a Contributor floor when the trust ladder landed (migration 087).
    await client.query(
      `INSERT INTO users (provider, provider_user_id, email, display_name, role)
       VALUES ($1, $2, $3, $4, 'contributors')
       ON CONFLICT (provider, provider_user_id)
       DO UPDATE SET email = EXCLUDED.email, role = EXCLUDED.role`,
      [
        TEST_USER_PROVIDER,
        TEST_USER_PROVIDER_ID,
        "e2e@civicpatch.org",
        "E2E Test User",
      ],
    );

    // Jurisdiction. scraped_at set (NOW) so the review renders in RECONCILE mode
    // (old<->new diff panel). The baseline fixture below leaves scraped_at NULL.
    await client.query(
      `INSERT INTO jurisdictions (jurisdiction_ocdid, state, status, data, scraped_at)
       VALUES ($1, 'nj', 'active', '{"name":"E2E Test City","geoid":"0600001"}', NOW())
       ON CONFLICT (jurisdiction_ocdid)
       DO UPDATE SET state = EXCLUDED.state, data = EXCLUDED.data, scraped_at = EXCLUDED.scraped_at`,
      [TEST_JURISDICTION_OCDID],
    );

    await seedReviewCard(client, {
      requestId: TEST_REQUEST_ID,
      ocdid: TEST_JURISDICTION_OCDID,
      people: [
        {
          person_id: JANE_PERSON_ID,
          name: "Jane Smith",
          label: "Council Member",
        },
      ],
    });

    // Second card
    for (const [jOcdid, jName, reqId, prId, prNum, stateCode, geoidPrefix] of [
      [
        TEST_JURISDICTION_OCDID_2,
        "E2E Test City 2",
        TEST_REQUEST_ID_2,
        TEST_PR_ID_2,
        2,
        "nj",
        "060000",
      ],
      [
        TEST_JURISDICTION_OCDID_3,
        "E2E Test City 3",
        TEST_REQUEST_ID_3,
        TEST_PR_ID_3,
        3,
        "nj",
        "060000",
      ],
      [
        TX_JURISDICTION_OCDID,
        "E2E TX City",
        TX_REQUEST_ID,
        TX_PR_ID,
        10,
        "tx",
        "480000",
      ],
    ]) {
      await client.query(
        `INSERT INTO jurisdictions (jurisdiction_ocdid, state, status, data, scraped_at)
         VALUES ($1, $3, 'active', $2, NOW())
         ON CONFLICT (jurisdiction_ocdid) DO UPDATE SET state = EXCLUDED.state, data = EXCLUDED.data, scraped_at = EXCLUDED.scraped_at`,
        [
          jOcdid,
          JSON.stringify({ name: jName, geoid: `${geoidPrefix}${prNum}` }),
          stateCode,
        ],
      );
      await seedReviewCard(client, {
        requestId: reqId,
        ocdid: jOcdid,
        people: [
          {
            person_id: personIdFor(reqId),
            name: `${jName} Member`,
            label: "Council Member",
          },
        ],
      });
    }

    // Baseline card — scraped_at intentionally omitted (NULL) → BASELINE mode.
    await client.query(
      `INSERT INTO jurisdictions (jurisdiction_ocdid, state, status, data)
       VALUES ($1, 'vt', 'active', '{"name":"E2E Baseline City","geoid":"5000009"}')
       ON CONFLICT (jurisdiction_ocdid)
       DO UPDATE SET state = EXCLUDED.state, data = EXCLUDED.data`,
      [BASELINE_JURISDICTION_OCDID],
    );
    await seedReviewCard(client, {
      requestId: BASELINE_REQUEST_ID,
      ocdid: BASELINE_JURISDICTION_OCDID,
      people: [
        {
          person_id: personIdFor(BASELINE_REQUEST_ID),
          name: "Jane Baseline",
          label: "Council Member",
        },
      ],
    });

    // Populated reconcile card — scraped_at set → RECONCILE mode, with existing
    // people so the diff renders changed / added / removed states.
    await client.query(
      `INSERT INTO jurisdictions (jurisdiction_ocdid, state, status, data, scraped_at)
       VALUES ($1, 'nh', 'active', '{"name":"E2E Reconcile City","geoid":"3300001"}', NOW())
       ON CONFLICT (jurisdiction_ocdid)
       DO UPDATE SET state = EXCLUDED.state, data = EXCLUDED.data, scraped_at = EXCLUDED.scraped_at`,
      [RECONCILE_JURISDICTION_OCDID],
    );
    // Existing people: maria will be CHANGED, bob will be REMOVED. The `id` in
    // the JSONB is what computePeopleDiff pairs old<->new on.
    const reconcileExisting = [
      {
        id: "recon-maria",
        name: "Maria González",
        office: { name: "Mayor", division_ocdid: RECONCILE_DIVISION },
        emails: ["maria@nh.gov"],
        phones: ["(555) 010-0101"],
        urls: [],
        other_names: [],
        source_urls: ["https://example.gov/roster"],
        start_date: "2021",
        end_date: "2025",
        cdn_image: "https://cdn.test/maria.jpg",
      },
      {
        id: "recon-bob",
        name: "Bob Clerk",
        office: { name: "Clerk", division_ocdid: RECONCILE_DIVISION },
        emails: ["bob@nh.gov"],
        phones: [],
        urls: [],
        other_names: [],
        source_urls: ["https://example.gov/roster"],
      },
    ];
    // people PK is an auto-uuid, so re-seeding can't ON CONFLICT — clear first
    // to keep the row set deterministic if a prior run didn't tear down cleanly.
    await client.query(`DELETE FROM people WHERE jurisdiction_ocdid = $1`, [
      RECONCILE_JURISDICTION_OCDID,
    ]);
    for (const person of reconcileExisting) {
      await seedPerson(client, RECONCILE_JURISDICTION_OCDID, person);
    }
    // Proposed: maria changed (office + added email + removed phone), tom added.
    const reconcileProposed = [
      {
        id: "recon-maria",
        name: "Maria González",
        office: { name: "Council Member", division_ocdid: RECONCILE_DIVISION },
        emails: ["maria@nh.gov", "mayor@nh.gov"],
        phones: [],
        urls: [],
        other_names: [],
        source_urls: ["https://example.gov/roster"],
        start_date: "2021",
        end_date: "2025",
        image: "https://nh.gov/maria.jpg",
      },
      {
        id: "recon-tom",
        name: "Tom Treasurer",
        office: { name: "Treasurer", division_ocdid: RECONCILE_DIVISION },
        emails: ["tom@nh.gov"],
        phones: [],
        urls: [],
        other_names: [],
        source_urls: ["https://example.gov/roster"],
      },
    ];
    await seedReviewCard(client, {
      requestId: RECONCILE_REQUEST_ID,
      ocdid: RECONCILE_JURISDICTION_OCDID,
      people: asSightings(reconcileProposed),
    });

    // Scale card — 38 existing, 40 proposed (3 dropped, 5 added, 10 changed).
    await client.query(
      `INSERT INTO jurisdictions (jurisdiction_ocdid, state, status, data, scraped_at)
       VALUES ($1, 'ma', 'active', '{"name":"E2E Scale City","geoid":"2500001"}', NOW())
       ON CONFLICT (jurisdiction_ocdid)
       DO UPDATE SET state = EXCLUDED.state, data = EXCLUDED.data, scraped_at = EXCLUDED.scraped_at`,
      [SCALE_JURISDICTION_OCDID],
    );
    await client.query(`DELETE FROM people WHERE jurisdiction_ocdid = $1`, [
      SCALE_JURISDICTION_OCDID,
    ]);
    for (const person of buildScaleExisting()) {
      await seedPerson(client, SCALE_JURISDICTION_OCDID, person);
    }
    // Issues too, so the collapse rule's "an anchored issue keeps a field
    // visible" path is exercised at density, not only on a three-person card.
    const scaleReview = {
      issues: [
        {
          code: "duplicate_unique_role",
          message:
            "Role 'council president' is marked as unique but found in multiple officials: Councillor 09 Scale, Councillor 21 Scale",
          person_ids: ["scale-p09", "scale-p21"],
          field: "office.name",
        },
        {
          code: "new_official",
          message: "Extra official: Newcomer 05 Scale",
          person_ids: ["scale-n05"],
          field: null,
        },
      ],
    };
    await seedReviewCard(client, {
      requestId: SCALE_REQUEST_ID,
      ocdid: SCALE_JURISDICTION_OCDID,
      people: asSightings(buildScaleProposed()),
    });

    // Duplicate-id card — two proposed people share `dup-shared`.
    await client.query(
      `INSERT INTO jurisdictions (jurisdiction_ocdid, state, status, data, scraped_at)
       VALUES ($1, 'nm', 'active', '{"name":"E2E Duplicate City","geoid":"3500001"}', NOW())
       ON CONFLICT (jurisdiction_ocdid)
       DO UPDATE SET state = EXCLUDED.state, data = EXCLUDED.data, scraped_at = EXCLUDED.scraped_at`,
      [DUPLICATE_JURISDICTION_OCDID],
    );
    const duplicateDivision =
      "ocd-division/country:us/state:nm/place:e2e_duplicate";
    const duplicateProposed = [
      {
        id: "dup-shared",
        name: "Pat Duplicate",
        office: { name: "Mayor", division_ocdid: duplicateDivision },
        emails: [],
        phones: [],
        urls: [],
        other_names: [],
        source_urls: ["https://example.gov/roster"],
      },
      {
        id: "dup-shared",
        name: "Pat Duplicate the Second",
        office: { name: "Clerk", division_ocdid: duplicateDivision },
        emails: [],
        phones: [],
        urls: [],
        other_names: [],
        source_urls: ["https://example.gov/roster"],
      },
      {
        id: "dup-unique",
        name: "Sam Single",
        office: { name: "Treasurer", division_ocdid: duplicateDivision },
        emails: [],
        phones: [],
        urls: [],
        other_names: [],
        source_urls: ["https://example.gov/roster"],
      },
    ];
    await seedReviewCard(client, {
      requestId: DUPLICATE_REQUEST_ID,
      ocdid: DUPLICATE_JURISDICTION_OCDID,
      people: asSightings(duplicateProposed),
    });

    // Issue-markers card — reconcile mode, all proposed render as added cards.
    await client.query(
      `INSERT INTO jurisdictions (jurisdiction_ocdid, state, status, data, scraped_at)
       VALUES ($1, 'me', 'active', '{"name":"E2E Markers City","geoid":"2300001"}', NOW())
       ON CONFLICT (jurisdiction_ocdid)
       DO UPDATE SET state = EXCLUDED.state, data = EXCLUDED.data, scraped_at = EXCLUDED.scraped_at`,
      [MARKERS_JURISDICTION_OCDID],
    );
    // Alice & Bob both hold "Mayor" (the duplicated unique role); Carol is the extra.
    const markersProposed = [
      {
        id: "markers-alice",
        name: "Alice Mayor",
        office: { name: "Mayor", division_ocdid: MARKERS_DIVISION },
        emails: [],
        phones: [],
        urls: [],
        other_names: [],
        source_urls: ["https://example.gov/roster"],
      },
      {
        id: "markers-bob",
        name: "Bob Council",
        office: { name: "Mayor", division_ocdid: MARKERS_DIVISION },
        emails: [],
        phones: [],
        urls: [],
        other_names: [],
        source_urls: ["https://example.gov/roster"],
      },
      {
        id: "markers-carol",
        name: "Carol Extra",
        office: { name: "Council Member", division_ocdid: MARKERS_DIVISION },
        emails: [],
        phones: [],
        urls: [],
        other_names: [],
        source_urls: ["https://example.gov/roster"],
      },
    ];
    // new_official → row-level marker (Carol); duplicate_unique_role → field-level
    // marker under Office (Alice + Bob); absent_official → list-level (no card marker).
    const markersReview = {
      issues: [
        {
          code: "new_official",
          message: "Extra official: Carol Extra",
          person_ids: ["markers-carol"],
          field: null,
        },
        {
          code: "duplicate_unique_role",
          message:
            "Role 'mayor' is marked as unique but found in multiple officials: Alice Mayor, Bob Council",
          person_ids: ["markers-alice", "markers-bob"],
          field: "office.name",
        },
        {
          code: "absent_official",
          message: "Dropped official: Dave Absent",
          person_ids: [],
          field: null,
        },
      ],
      // The drawer's since-last-scrape table, matching the issues above:
      // Carol is the extra official (this scrape only), Dave the dropped one
      // (baseline only), Alice appears on both sides and needs no decision.
      people_by_source: [
        { name: "Carol Extra", in_research: false, in_data: true },
        { name: "Dave Absent", in_research: true, in_data: false },
        { name: "Alice Mayor", in_research: true, in_data: true },
      ],
    };
    await seedReviewCard(client, {
      requestId: MARKERS_REQUEST_ID,
      ocdid: MARKERS_JURISDICTION_OCDID,
      people: asSightings(markersProposed),
    });

    // Read-only card — merged PR, so the card renders in its terminal state.
    // `url` on the jurisdiction data is what surfaces as the website link.
    await client.query(
      `INSERT INTO jurisdictions (jurisdiction_ocdid, state, status, data, scraped_at)
       VALUES ($1, 'ri', 'active', $2, NOW())
       ON CONFLICT (jurisdiction_ocdid)
       DO UPDATE SET state = EXCLUDED.state, data = EXCLUDED.data, scraped_at = EXCLUDED.scraped_at`,
      [
        READ_ONLY_JURISDICTION_OCDID,
        JSON.stringify({
          name: "E2E Read Only City",
          geoid: "4400014",
          url: READ_ONLY_WEBSITE_URL,
        }),
      ],
    );
    await seedReviewCard(client, {
      requestId: READ_ONLY_REQUEST_ID,
      ocdid: READ_ONLY_JURISDICTION_OCDID,
      publishedAt: new Date().toISOString(),
      people: [
        {
          person_id: "e2e-jane-published",
          name: "Jane Published",
          label: "Council Member",
          email: "jane@ri.gov",
          phone: "(555) 040-0001",
          image: "https://ri.gov/jane.jpg",
          start_date: "2022",
        },
      ],
    });

    // Map status fixtures — one per bucket (fresh / stale / gap / untracked).
    // The presence of a `url` and a `people` row drives the status the map paints.
    const STALE_DAYS = 200; // > FRESH_THRESHOLD_DAYS (90)
    for (const [ocdid, name, hasUrl, peopleAgeDays] of [
      [MAP_FIXTURES.fresh, "E2E Map Fresh", true, 0],
      [MAP_FIXTURES.stale, "E2E Map Stale", true, STALE_DAYS],
      [MAP_FIXTURES.gap, "E2E Map Gap", true, null],
      [MAP_FIXTURES.untracked, "E2E Map Untracked", false, null],
    ]) {
      const data = hasUrl
        ? {
            name,
            url: `https://example.test/${name.replace(/\s+/g, "-").toLowerCase()}`,
          }
        : { name };
      await client.query(
        `INSERT INTO jurisdictions (jurisdiction_ocdid, state, status, data)
         VALUES ($1, 'nj', 'active', $2)
         ON CONFLICT (jurisdiction_ocdid) DO UPDATE SET state = EXCLUDED.state, data = EXCLUDED.data`,
        [ocdid, JSON.stringify(data)],
      );
      if (peopleAgeDays !== null) {
        await client.query(
          `INSERT INTO people (jurisdiction_ocdid, name, updated_at)
           VALUES ($1, 'E2E Person', NOW() - ($2 || ' days')::interval)`,
          [ocdid, peopleAgeDays],
        );
      }
    }

    // One `unrecognized_role` issue, so the issues page has a row whose Resolve
    // button opens the config editor. That modal is the only place
    // config-editor.css renders, and it holds the largest remaining cluster of
    // Pico overrides — without this row the visual baseline cannot see it.
    //
    // `jurisdictions` on the API response is derived from the request's
    // jurisdiction_ocdid, so pointing at TEST_REQUEST_ID is what makes the
    // button appear at all (issue-row.js renders it only when the issue is
    // unrecognized_role AND carries jurisdictions).
    await client.query(
      `INSERT INTO issues (issue_type, issue_key, request_ids, data, status)
       VALUES ('unrecognized_role', $1, ARRAY[$2], $3, 'pending')
       ON CONFLICT (issue_type, issue_key) DO UPDATE
         SET request_ids = EXCLUDED.request_ids,
             data = EXCLUDED.data,
             status = EXCLUDED.status`,
      [
        UNRECOGNIZED_ROLE_KEY,
        TEST_REQUEST_ID,
        JSON.stringify({ person_names: ["Jane Smith"] }),
      ],
    );
  } finally {
    await client.end();
  }
}

export async function teardownE2eFixtures() {
  const client = makeClient();
  await client.connect();
  try {
    await client.query(
      `DELETE FROM issues WHERE issue_type = 'unrecognized_role' AND issue_key = $1`,
      [UNRECOGNIZED_ROLE_KEY],
    );

    // Delete in reverse FK order
    await client.query(
      `DELETE FROM review_session_entries
       WHERE review_session_id IN (
         SELECT id FROM review_sessions WHERE user_id = (
           SELECT id FROM users WHERE provider = $1 AND provider_user_id = $2
         )
       )`,
      [TEST_USER_PROVIDER, TEST_USER_PROVIDER_ID],
    );
    await client.query(
      `DELETE FROM review_sessions WHERE user_id = (
         SELECT id FROM users WHERE provider = $1 AND provider_user_id = $2
       )`,
      [TEST_USER_PROVIDER, TEST_USER_PROVIDER_ID],
    );
    // The reconcile and scale fixtures seed people; clear them before their
    // jurisdiction rows.
    await client.query(`DELETE FROM people WHERE jurisdiction_ocdid = $1`, [
      RECONCILE_JURISDICTION_OCDID,
    ]);
    await client.query(`DELETE FROM people WHERE jurisdiction_ocdid = $1`, [
      SCALE_JURISDICTION_OCDID,
    ]);
    for (const [prId, reqId, jOcdid] of [
      [TEST_PR_ID, TEST_REQUEST_ID, TEST_JURISDICTION_OCDID],
      [TEST_PR_ID_2, TEST_REQUEST_ID_2, TEST_JURISDICTION_OCDID_2],
      [TEST_PR_ID_3, TEST_REQUEST_ID_3, TEST_JURISDICTION_OCDID_3],
      [BASELINE_PR_ID, BASELINE_REQUEST_ID, BASELINE_JURISDICTION_OCDID],
      [RECONCILE_PR_ID, RECONCILE_REQUEST_ID, RECONCILE_JURISDICTION_OCDID],
      [SCALE_PR_ID, SCALE_REQUEST_ID, SCALE_JURISDICTION_OCDID],
      [DUPLICATE_PR_ID, DUPLICATE_REQUEST_ID, DUPLICATE_JURISDICTION_OCDID],
      [TX_PR_ID, TX_REQUEST_ID, TX_JURISDICTION_OCDID],
      [MARKERS_PR_ID, MARKERS_REQUEST_ID, MARKERS_JURISDICTION_OCDID],
      [READ_ONLY_PR_ID, READ_ONLY_REQUEST_ID, READ_ONLY_JURISDICTION_OCDID],
    ]) {
      // source_records cascades from requests; identities cascade from source_records.
      await client.query(`DELETE FROM requests WHERE id = $1`, [reqId]);
      await client.query(
        `DELETE FROM jurisdictions WHERE jurisdiction_ocdid = $1`,
        [jOcdid],
      );
    }
    for (const ocdid of Object.values(MAP_FIXTURES)) {
      await client.query(`DELETE FROM people WHERE jurisdiction_ocdid = $1`, [
        ocdid,
      ]);
      await client.query(
        `DELETE FROM jurisdictions WHERE jurisdiction_ocdid = $1`,
        [ocdid],
      );
    }
    for (const [code] of STATE_JURISDICTIONS) {
      await client.query(
        `DELETE FROM jurisdictions WHERE jurisdiction_ocdid = $1`,
        [stateOcdid(code)],
      );
    }
    await client.query(
      `DELETE FROM users WHERE provider = $1 AND provider_user_id = $2`,
      [TEST_USER_PROVIDER, TEST_USER_PROVIDER_ID],
    );
  } finally {
    await client.end();
  }
}
