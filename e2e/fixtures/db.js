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
export const TEST_CHANGESET_ID = "00000000-0000-0000-eeee-000000000001";
// person_id is a uuid since migration 144 — the old "e2e-jane" style fails at the insert now.
export const JANE_PERSON_ID = "00000000-0000-0000-aaaa-000000000001";

/** A deterministic person uuid per request, so teardown and assertions can both find it. */
function personIdFor(changesetId) {
  return "00000000-0000-0000-aaaa-" + changesetId.slice(-12);
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * Fixture people are named by readable slugs — "recon-maria", "dup-shared" — but
 * `source_record_identities.person_id` became a uuid in migration 144, so the slug can no
 * longer be inserted. Hashing keeps the fixtures readable and stable: the same slug always
 * yields the same id, which is what lets two sightings deliberately share a person.
 */
export function personUuid(slug) {
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
export const TEST_CHANGESET_ID_2 = "00000000-0000-0000-eeee-000000000003";
const TEST_PR_ID_2 = "00000000-0000-0000-eeee-000000000004";

export const TEST_JURISDICTION_OCDID_3 =
  "ocd-jurisdiction/country:us/state:nj/place:e2e_test_3/government";
export const TEST_CHANGESET_ID_3 = "00000000-0000-0000-eeee-000000000005";
const TEST_PR_ID_3 = "00000000-0000-0000-eeee-000000000006";

// Baseline fixture — a first-capture jurisdiction (scraped_at left NULL) so the
// review renders in BASELINE mode (banner, no diff panel). The baseline-mode spec
// deep-links to it by changeset_id. Kept in its own state (vt) so this extra open
// card doesn't pollute the nj review queue the state-switching specs count on.
export const BASELINE_JURISDICTION_OCDID =
  "ocd-jurisdiction/country:us/state:vt/place:e2e_baseline/government";
export const BASELINE_CHANGESET_ID = "00000000-0000-0000-eeee-000000000007";
const BASELINE_PR_ID = "00000000-0000-0000-eeee-000000000008";
const BASELINE_PR_NUMBER = 4;

// Populated reconcile fixture — a previously-scraped jurisdiction (scraped_at
// set) with existing people, so the diff renders real changed/added/removed
// states. Own state (vt2 → "nh") and deep-linked by changeset_id, like baseline.
export const RECONCILE_JURISDICTION_OCDID =
  "ocd-jurisdiction/country:us/state:nh/place:e2e_reconcile/government";
export const RECONCILE_CHANGESET_ID = "00000000-0000-0000-eeee-000000000009";
const RECONCILE_PR_ID = "00000000-0000-0000-eeee-00000000000a";
const RECONCILE_PR_NUMBER = 5;

// Scale fixture — a realistically-sized council (§20). Every other card here has
// two or three people, which makes the layout questions the redesign exists to
// answer unfalsifiable: whether the collapse rule earns its keep, whether the
// editor becomes an unusable scroll, whether the grid holds at density. Own state
// (ma) so this large open card stays out of every other spec's review queue.
export const SCALE_JURISDICTION_OCDID =
  "ocd-jurisdiction/country:us/state:ma/place:e2e_scale/government";
export const SCALE_CHANGESET_ID = "00000000-0000-0000-eeee-00000000000f";
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
    phones: [`(201) 555-01${n}`],
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
        // An added email — two sightings of one person, which `asSightings` emits.
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

// TX fixture — minimal data so cross-state isolation tests can positively
// assert TX content (not just the absence of NJ content).
export const TX_JURISDICTION_OCDID =
  "ocd-jurisdiction/country:us/state:tx/place:e2e_tx/government";
export const TX_CHANGESET_ID = "00000000-0000-0000-eeee-000000000010";
const TX_PR_ID = "00000000-0000-0000-eeee-000000000011";

// Issue-markers fixture — reconcile mode (scraped_at set), no existing people so
// every proposed person renders as an "added" card. Its issues carry
// structured issues that anchor to proposed person ids, exercising the review card's
// per-card markers. Own state (me) and deep-linked by changeset_id, like the others.
export const MARKERS_JURISDICTION_OCDID =
  "ocd-jurisdiction/country:us/state:me/place:e2e_markers/government";
export const MARKERS_CHANGESET_ID = "00000000-0000-0000-eeee-000000000012";
const MARKERS_PR_ID = "00000000-0000-0000-eeee-000000000013";
const MARKERS_PR_NUMBER = 12;

// Read-only fixture — a published request, the state a card lands in once it has
// been published. It is the only fixture with published_at set, so the only one that
// renders the terminal-status banner, the open-data link and the jurisdiction website
// link, and that hides the publish/save/close actions. Its request is still
// 'merged' because the card's link still reads PR metadata.
// Own state (ri) and deep-linked by changeset_id: a published request is out of the
// review pool, so it is only reachable by link, which is how reviewers reach it too.
export const READ_ONLY_JURISDICTION_OCDID =
  "ocd-jurisdiction/country:us/state:ri/place:e2e_read_only/government";
export const READ_ONLY_CHANGESET_ID = "00000000-0000-0000-eeee-000000000014";
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
// A sighting carries label text, and the roster derives the division by parsing it — a raw
// `division_ocdid` on the sighting is discarded. So a ward seat has to be spelled out, or the
// seat derives to the jurisdiction's own division while `seatPerson` seated them in a ward,
// and every carried person reads as moved.
function sightingLabel(office) {
  if (!office?.name) return "";
  const ward = office.division_ocdid?.match(/\/ward:(.+)$/)?.[1];
  return ward ? `${office.name} Ward ${ward}` : office.name;
}

// One sighting per email: a sighting is one appearance on one page and carries one contact, so
// somebody listed with two addresses was seen twice. `roster_from_sightings` groups by person and
// merges them — which is the only way a fixture can propose an *added* value, and the
// multi-value provenance tests depend on it.
function asSightings(proposed) {
  return proposed.flatMap(function (person) {
    const emails = person.emails?.length ? person.emails : [null];
    return emails.map(function (email) {
      return {
        person_id: person.id,
        name: person.name,
        label: sightingLabel(person.office),
        email,
        phone: person.phones?.[0] ?? null,
        url: person.urls?.[0] ?? null,
        image: person.image ?? null,
        start_date: person.start_date ?? null,
        end_date: person.end_date ?? null,
      };
    });
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
  { changesetId, ocdid, people = [], publishedAt = null, ageSeconds = 0, changeUrl = null },
) {
  await client.query(
    // `ageSeconds` makes the queue order intentional rather than an accident of insertion
    // time. The queue sorts `created_at DESC`, and cards seeded in one run otherwise share a
    // timestamp to the microsecond — so which card a session opened first was arbitrary.
    // Age 0 is the newest, and therefore the first card a review session offers.
    // `change_url` is where the change landed. It used to live on `pull_requests`, which
    // migration 141 dropped — so a published card had no url to link to and the review page
    // simply rendered no link.
    `INSERT INTO changesets (id, kind, jurisdiction_ocdid, arguments_json,
                           status, progress, sourced_at, created_at, published_at, change_url)
     VALUES ($1, 'scrape', $2, '{}', 'success', 100, NOW(),
             NOW() - ($4 * INTERVAL '1 second'), $3, $5)
     ON CONFLICT (id) DO NOTHING`,
    [changesetId, ocdid, publishedAt, ageSeconds, changeUrl],
  );
  // Re-seeding must not double the sightings: source_records has an auto id, so there is
  // nothing to ON CONFLICT on.
  await client.query(`DELETE FROM source_records WHERE changeset_id = $1`, [
    changesetId,
  ]);
  for (const person of people) {
    const { rows } = await client.query(
      `INSERT INTO source_records (changeset_id, jurisdiction_ocdid, name, label, source_url,
                                   url, phone, email, image, start_date, end_date)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
       RETURNING id`,
      [
        changesetId,
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

// Whether somebody is seated is a memberships question, and `get_roster` — which is what the
// review card sends as `existing` — filters on `IS_ON_THE_ROSTER`: an open membership. A person
// row alone is invisible to it, so every proposed person diffs as `added` and no card ever
// collapses to a strip. Seating needs four rows, because a membership points at a post, a post
// at an organization and a division, and `posts.role_id` is a real FK.
const SEAT_ROLE_FALLBACK = "council-member";

const roleSlug = (name) =>
  (name || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");

async function seatPerson(client, ocdid, person) {
  const { rows: org } = await client.query(
    `WITH found AS (SELECT id FROM organizations WHERE jurisdiction_ocdid = $1 LIMIT 1),
          made AS (INSERT INTO organizations (jurisdiction_ocdid, name)
                   SELECT $1, 'Council' WHERE NOT EXISTS (SELECT 1 FROM found)
                   RETURNING id)
     SELECT id FROM found UNION ALL SELECT id FROM made`,
    [ocdid],
  );
  const organizationId = org[0].id;

  // The person's own ward when the fixture gave them one, else the jurisdiction itself.
  const division = person.office?.division_ocdid ?? ocdid.replace("/government", "");
  await client.query(
    `INSERT INTO divisions (ocdid, jurisdiction_ocdid) VALUES ($1, $2)
     ON CONFLICT (ocdid) DO NOTHING`,
    [division, ocdid],
  );

  // Fall back rather than fail: a fixture office that slugs to no seeded role would otherwise
  // break seeding on a foreign key, which reads as a schema fault rather than a fixture one.
  const wanted = roleSlug(person.office?.name);
  const { rows: role } = await client.query(`SELECT id FROM roles WHERE id = $1`, [
    wanted,
  ]);
  const roleId = role.length ? wanted : SEAT_ROLE_FALLBACK;

  const { rows: post } = await client.query(
    `INSERT INTO posts (jurisdiction_ocdid, organization_id, role_id, division_ocdid)
     VALUES ($1, $2, $3, $4)
     ON CONFLICT (organization_id, role_id, division_ocdid)
       DO UPDATE SET role_id = EXCLUDED.role_id
     RETURNING id`,
    [ocdid, organizationId, roleId, division],
  );

  // Term dates live on the membership, not on `people` — `PERSON_START_DATE` reads
  // `memberships.start_date`. Seeding them only on the person left every existing record with
  // null terms, so every proposed person differed on Term start / Term end and nothing folded.
  await client.query(
    `INSERT INTO memberships (post_id, organization_id, person_id, start_date, end_date,
                              first_seen_at, last_seen_at)
     VALUES ($1, $2, $3, $4, $5, NOW(), NOW())
     ON CONFLICT (person_id, organization_id) WHERE closed_at IS NULL DO NOTHING`,
    [
      post[0].id,
      organizationId,
      personUuid(person.id),
      person.start_date ?? null,
      person.end_date ?? null,
    ],
  );
}

/** A jurisdiction's whole roster: the people and the four rows that seat them.
 *
 *  Order is load-bearing and none of these cascade — a membership points at a person and a
 *  post, a post at an organization and a division, and all three at the jurisdiction. Deleting
 *  people (or the jurisdiction) first fails on a foreign key.
 */
async function clearRoster(client, ocdid) {
  await client.query(
    `DELETE FROM memberships WHERE post_id IN
       (SELECT id FROM posts WHERE jurisdiction_ocdid = $1)
        OR person_id IN (SELECT id FROM people WHERE jurisdiction_ocdid = $1)`,
    [ocdid],
  );
  await client.query(`DELETE FROM posts WHERE jurisdiction_ocdid = $1`, [ocdid]);
  await client.query(`DELETE FROM organizations WHERE jurisdiction_ocdid = $1`, [
    ocdid,
  ]);
  await client.query(`DELETE FROM divisions WHERE jurisdiction_ocdid = $1`, [ocdid]);
  await client.query(`DELETE FROM people WHERE jurisdiction_ocdid = $1`, [ocdid]);
}

/** A published person. `people.data` and `people.status` are gone — these are real columns now,
 *  and whether somebody is seated is a memberships question, answered by `seatPerson`. */
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
  await seatPerson(client, ocdid, person);
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
      changesetId: TEST_CHANGESET_ID,
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
        TEST_CHANGESET_ID_2,
        TEST_PR_ID_2,
        2,
        "nj",
        "060000",
      ],
      [
        TEST_JURISDICTION_OCDID_3,
        "E2E Test City 3",
        TEST_CHANGESET_ID_3,
        TEST_PR_ID_3,
        3,
        "nj",
        "060000",
      ],
      [
        TX_JURISDICTION_OCDID,
        "E2E TX City",
        TX_CHANGESET_ID,
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
        changesetId: reqId,
        ocdid: jOcdid,
        // City 1 newest, so it is the first card — which is what the review specs assert.
        ageSeconds: prNum,
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
      changesetId: BASELINE_CHANGESET_ID,
      ocdid: BASELINE_JURISDICTION_OCDID,
      people: [
        {
          person_id: personIdFor(BASELINE_CHANGESET_ID),
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
        phones: ["(201) 555-0102"],
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
    await clearRoster(client, RECONCILE_JURISDICTION_OCDID);
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
        // A new term end, so one scalar field actually moves. The seat moved too, but the seat
        // is a picked post: it has no old value on the record to annotate, so it can carry an
        // issue and not a `was`. Term end is what keeps the `was` / Restore claims testable.
        end_date: "2029",
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
      changesetId: RECONCILE_CHANGESET_ID,
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
    await clearRoster(client, SCALE_JURISDICTION_OCDID);
    for (const person of buildScaleExisting()) {
      await seedPerson(client, SCALE_JURISDICTION_OCDID, person);
    }
    await seedReviewCard(client, {
      changesetId: SCALE_CHANGESET_ID,
      ocdid: SCALE_JURISDICTION_OCDID,
      people: asSightings(buildScaleProposed()),
    });

    // Issue-markers card — reconcile mode, all proposed render as added cards.
    await client.query(
      `INSERT INTO jurisdictions (jurisdiction_ocdid, state, status, data, scraped_at)
       VALUES ($1, 'me', 'active', '{"name":"E2E Markers City","geoid":"2300001"}', NOW())
       ON CONFLICT (jurisdiction_ocdid)
       DO UPDATE SET state = EXCLUDED.state, data = EXCLUDED.data, scraped_at = EXCLUDED.scraped_at`,
      [MARKERS_JURISDICTION_OCDID],
    );
    // Alice, Bob and Dave are already published here; the scrape finds Alice, Bob and Carol.
    // That is what makes each issue kind reachable: Carol is new, Dave is absent, and Alice and
    // Bob both hold "Mayor" — the duplicated unique role. Seeding only the proposed side made
    // all three read as new_person and produced no absent_person at all.
    const markersPublished = [
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
        id: "markers-dave",
        name: "Dave Absent",
        office: { name: "Clerk", division_ocdid: MARKERS_DIVISION },
        emails: [],
        phones: [],
        urls: [],
        other_names: [],
        source_urls: ["https://example.gov/roster"],
      },
    ];
    await clearRoster(client, MARKERS_JURISDICTION_OCDID);
    for (const person of markersPublished) {
      await seedPerson(client, MARKERS_JURISDICTION_OCDID, person);
    }
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
    await seedReviewCard(client, {
      changesetId: MARKERS_CHANGESET_ID,
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
      changesetId: READ_ONLY_CHANGESET_ID,
      ocdid: READ_ONLY_JURISDICTION_OCDID,
      publishedAt: new Date().toISOString(),
      changeUrl: READ_ONLY_PR_URL,
      people: [
        {
          person_id: "e2e-jane-published",
          name: "Jane Published",
          label: "Council Member",
          email: "jane@ri.gov",
          phone: "(201) 555-0103",
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
    // jurisdiction_ocdid, so pointing at TEST_CHANGESET_ID is what makes the
    // button appear at all (issue-row.js renders it only when the issue is
    // unrecognized_role AND carries jurisdictions).
    await client.query(
      `INSERT INTO issues (issue_type, issue_key, changeset_ids, data, status)
       VALUES ('unrecognized_role', $1, ARRAY[$2], $3, 'pending')
       ON CONFLICT (issue_type, issue_key) DO UPDATE
         SET changeset_ids = EXCLUDED.changeset_ids,
             data = EXCLUDED.data,
             status = EXCLUDED.status`,
      [
        UNRECOGNIZED_ROLE_KEY,
        TEST_CHANGESET_ID,
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
    await clearRoster(client, RECONCILE_JURISDICTION_OCDID);
    await clearRoster(client, SCALE_JURISDICTION_OCDID);
    for (const [prId, reqId, jOcdid] of [
      [TEST_PR_ID, TEST_CHANGESET_ID, TEST_JURISDICTION_OCDID],
      [TEST_PR_ID_2, TEST_CHANGESET_ID_2, TEST_JURISDICTION_OCDID_2],
      [TEST_PR_ID_3, TEST_CHANGESET_ID_3, TEST_JURISDICTION_OCDID_3],
      [BASELINE_PR_ID, BASELINE_CHANGESET_ID, BASELINE_JURISDICTION_OCDID],
      [RECONCILE_PR_ID, RECONCILE_CHANGESET_ID, RECONCILE_JURISDICTION_OCDID],
      [SCALE_PR_ID, SCALE_CHANGESET_ID, SCALE_JURISDICTION_OCDID],
      [TX_PR_ID, TX_CHANGESET_ID, TX_JURISDICTION_OCDID],
      [MARKERS_PR_ID, MARKERS_CHANGESET_ID, MARKERS_JURISDICTION_OCDID],
      [READ_ONLY_PR_ID, READ_ONLY_CHANGESET_ID, READ_ONLY_JURISDICTION_OCDID],
    ]) {
      // source_records cascades from changesets; identities cascade from source_records.
      await client.query(`DELETE FROM changesets WHERE id = $1`, [reqId]);
      await clearRoster(client, jOcdid);
      await client.query(
        `DELETE FROM jurisdictions WHERE jurisdiction_ocdid = $1`,
        [jOcdid],
      );
    }
    for (const ocdid of Object.values(MAP_FIXTURES)) {
      await clearRoster(client, ocdid);
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
