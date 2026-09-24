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
/** The division a jurisdiction's own posts sit in, spelled the way the fold spells it.
 *
 * Not `ocdid.replace("/government", "")`: that leaves an `ocd-jurisdiction/...` id, and the
 * fold derives `ocd-division/...` (`shared/utils/divisions.py`). Two spellings mean two posts
 * for one office, and then the card's derived side and the stored side name different ids. */
export const divisionOf = (ocdid) =>
  ocdid.replace(/^ocd-jurisdiction/, "ocd-division").replace(/\/government$/, "");

// `core/projection/facts.py::POST_NAMESPACE`. A post's id is derived, not assigned, so a
// fixture that wants the fold to recognise its post has to compute the same uuid5.
const POST_NAMESPACE = "c8374c67-da4d-4aac-a0d9-4f353c803eca";

/** RFC 4122 uuid5, byte for byte what Python's `uuid.uuid5` produces. */
export function postUuid(organizationId, roleId, divisionOcdid) {
  const namespace = Buffer.from(POST_NAMESPACE.replace(/-/g, ""), "hex");
  const name = Buffer.from(`${organizationId}|${roleId}|${divisionOcdid}`, "utf8");
  const hash = crypto.createHash("sha1").update(Buffer.concat([namespace, name])).digest();
  const bytes = Buffer.from(hash.subarray(0, 16));
  bytes[6] = (bytes[6] & 0x0f) | 0x50;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = bytes.toString("hex");
  return [
    hex.slice(0, 8),
    hex.slice(8, 12),
    hex.slice(12, 16),
    hex.slice(16, 20),
    hex.slice(20, 32),
  ].join("-");
}

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


export const TEST_JURISDICTION_OCDID_2 =
  "ocd-jurisdiction/country:us/state:nj/place:e2e_test_2/government";
export const TEST_CHANGESET_ID_2 = "00000000-0000-0000-eeee-000000000003";

export const TEST_JURISDICTION_OCDID_3 =
  "ocd-jurisdiction/country:us/state:nj/place:e2e_test_3/government";
export const TEST_CHANGESET_ID_3 = "00000000-0000-0000-eeee-000000000005";

// Baseline fixture — a first-capture jurisdiction (no prior collection) so the
// review renders in BASELINE mode (banner, no diff panel). The baseline-mode spec
// deep-links to it by changeset_id. Kept in its own state (vt) so this extra open
// card doesn't pollute the nj review queue the state-switching specs count on.
export const BASELINE_JURISDICTION_OCDID =
  "ocd-jurisdiction/country:us/state:vt/place:e2e_baseline/government";
export const BASELINE_CHANGESET_ID = "00000000-0000-0000-eeee-000000000007";
const BASELINE_PR_NUMBER = 4;

// Populated reconcile fixture — a previously-collected jurisdiction with existing
// people, so the diff renders real changed/added/removed
// states. Own state (vt2 → "nh") and deep-linked by changeset_id, like baseline.
export const RECONCILE_JURISDICTION_OCDID =
  "ocd-jurisdiction/country:us/state:nh/place:e2e_reconcile/government";
export const RECONCILE_CHANGESET_ID = "00000000-0000-0000-eeee-000000000009";
const RECONCILE_PR_NUMBER = 5;

// Scale fixture — a realistically-sized council (§20). Every other card here has
// two or three people, which makes the layout questions the redesign exists to
// answer unfalsifiable: whether the collapse rule earns its keep, whether the
// editor becomes an unusable scroll, whether the grid holds at density. Own state
// (ma) so this large open card stays out of every other spec's review queue.
export const SCALE_JURISDICTION_OCDID =
  "ocd-jurisdiction/country:us/state:ma/place:e2e_scale/government";
export const SCALE_CHANGESET_ID = "00000000-0000-0000-eeee-00000000000f";
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

// Attempts, not proposals: an in-flight or failed run has `changeset_id` NULL, so it appears
// in no changeset-rooted query. nj is busy and has failed once, tx has only failed.
const NJ_RUN_IN_FLIGHT_ID = "00000000-0000-0000-dddd-000000000001";
const NJ_RUN_FAILED_ID = "00000000-0000-0000-dddd-000000000002";
const TX_RUN_FAILED_ID = "00000000-0000-0000-dddd-000000000003";
const SEEDED_RUN_IDS = [
  NJ_RUN_IN_FLIGHT_ID,
  NJ_RUN_FAILED_ID,
  TX_RUN_FAILED_ID,
];

// Issue-markers fixture — reconcile mode (a prior collection), no existing people so
// every proposed person renders as an "added" card. Its issues carry
// structured issues that anchor to proposed person ids, exercising the review card's
// per-card markers. Own state (me) and deep-linked by changeset_id, like the others.
export const MARKERS_JURISDICTION_OCDID =
  "ocd-jurisdiction/country:us/state:me/place:e2e_markers/government";
export const MARKERS_CHANGESET_ID = "00000000-0000-0000-eeee-000000000012";
const MARKERS_PR_NUMBER = 12;

// Read-only fixture — a published request, the state a card lands in once it has
// been published. It is the only fixture with published_at set, so the only one that
// renders the terminal-status banner, the open-data link and the jurisdiction website
// link, and that hides the publish/save/close actions. Its request is still
// 'merged' because the card's link still reads PR metadata.
// Own state (ri) and deep-linked by changeset_id: a published request is out of the
// review pool, so it is only reachable by link, which is how reviewers reach it too.
// One person holding an office in two bodies — the case the roster editor grouped wrong until
// 2026-09-23, when it filed them silently under whichever body sorted first.
// Own state (md), like every other fixture jurisdiction: in NJ it was a fourth locality in
// the list `municipalities-page.spec.js` counts.
export const TWO_BODY_JURISDICTION_OCDID =
  "ocd-jurisdiction/country:us/state:md/place:e2e_two_body/government";
export const TWO_BODY_COUNCIL = "E2E Council";
export const TWO_BODY_SCHOOL_BOARD = "E2E School Board";
// A scrape that read two bodies in one changeset, with one person in both. The review card was
// built assuming a changeset is one organization; this is the fixture that says otherwise.
// Its own jurisdiction on purpose: an unpublished changeset puts a jurisdiction into review,
// and `peopleEditBlockers` then switches roster editing off — which would make the two-body
// *roster* fixture untestable. Own state (de) for the usual reason: this card is open, so in
// NJ it joined every other spec's review queue and became "the first card".
export const TWO_ORG_JURISDICTION_OCDID =
  "ocd-jurisdiction/country:us/state:de/place:e2e_two_org/government";
export const TWO_ORG_CHANGESET_ID = "00000000-0000-0000-eeee-000000000016";

export const READ_ONLY_JURISDICTION_OCDID =
  "ocd-jurisdiction/country:us/state:ri/place:e2e_read_only/government";
export const READ_ONLY_CHANGESET_ID = "00000000-0000-0000-eeee-000000000014";
export const READ_ONLY_PR_URL =
  "https://github.com/civicpatch/open-data/pull/14";
export const READ_ONLY_WEBSITE_URL = "https://e2e-readonly.example.gov";
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
// What puts a card in RECONCILE rather than BASELINE mode: `has_ever_collected` asks whether the
// jurisdiction has a published changeset of a collection kind. Replaces `jurisdictions.scraped_at`
// (dropped by migration 181), so the fixture is previously collected rather than stamped.
const priorCollectionId = (ocdid) => personUuid(`prior-collection:${ocdid}`);

async function seedPriorCollection(client, ocdid) {
  await client.query(
    `INSERT INTO changesets (id, kind, jurisdiction_ocdid, created_at, updated_at, published_at)
     VALUES ($1, 'scrape', $2,
             NOW() - INTERVAL '30 days', NOW() - INTERVAL '30 days', NOW() - INTERVAL '30 days')
     ON CONFLICT (id) DO NOTHING`,
    [priorCollectionId(ocdid), ocdid],
  );
}

// The jurisdiction's organization, made when a seeded jurisdiction has none — every source record
// and post belongs to one.
async function organizationFor(client, ocdid) {
  const { rows } = await client.query(
    `WITH found AS (SELECT id FROM organizations WHERE jurisdiction_ocdid = $1 LIMIT 1),
          made AS (INSERT INTO organizations (jurisdiction_ocdid, name)
                   SELECT $1, 'Council' WHERE NOT EXISTS (SELECT 1 FROM found)
                   RETURNING id)
     SELECT id FROM found UNION ALL SELECT id FROM made`,
    [ocdid],
  );
  return rows[0].id;
}

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
    // `arguments_json`, `status` and `progress` left `changesets` in migration 170 — they
    // describe the run, which now has its own table. A changeset exists only because a run
    // already succeeded, so there is no status to seed here.
    `INSERT INTO changesets (id, kind, jurisdiction_ocdid,
                           created_at, updated_at, published_at, change_url)
     VALUES ($1, 'scrape', $2,
             NOW() - ($4 * INTERVAL '1 second'),
             NOW() - ($4 * INTERVAL '1 second'), $3, $5)
     ON CONFLICT (id) DO NOTHING`,
    [changesetId, ocdid, publishedAt, ageSeconds, changeUrl],
  );
  // Re-seeding must not double the sightings: source_records has an auto id, so there is
  // nothing to ON CONFLICT on.
  await client.query(`DELETE FROM source_records WHERE changeset_id = $1`, [
    changesetId,
  ]);
  const defaultOrganizationId = await organizationFor(client, ocdid);
  for (const person of people) {
    const organizationId = person.organization
      ? await namedOrganization(client, ocdid, person.organization)
      : defaultOrganizationId;
    const { rows } = await client.query(
      `INSERT INTO source_records (changeset_id, jurisdiction_ocdid, name, label, source_url,
                                   url, phone, email, image, start_date, end_date, organization_id)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
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
        organizationId,
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

/** The three rows a seat is: the division it is in, the post itself, and the membership.
 *
 * The post's id is the one the fold would derive, not a fresh one — the card's derived side
 * names posts by `PostKey`, so a fixture post with a random id is a different post from the
 * same office. Term dates live on the membership, not on `people`: `PERSON_START_DATE` reads
 * `memberships.start_date`, and seeding them on the person left every record with null terms,
 * so every proposed person differed on Term start / Term end and nothing folded.
 */
async function seatAt(client, ocdid, { organizationId, personId, roleId, division, startDate = null, endDate = null }) {
  await client.query(
    `INSERT INTO divisions (ocdid, jurisdiction_ocdid) VALUES ($1, $2)
     ON CONFLICT (ocdid) DO NOTHING`,
    [division, ocdid],
  );
  const { rows: post } = await client.query(
    `INSERT INTO posts (id, jurisdiction_ocdid, organization_id, role_id, division_ocdid)
     VALUES ($1, $2, $3, $4, $5)
     ON CONFLICT (organization_id, role_id, division_ocdid)
       DO UPDATE SET role_id = EXCLUDED.role_id
     RETURNING id`,
    [postUuid(organizationId, roleId, division), ocdid, organizationId, roleId, division],
  );
  await client.query(
    `INSERT INTO memberships (post_id, organization_id, person_id, start_date, end_date,
                              first_seen_at, last_seen_at)
     VALUES ($1, $2, $3, $4, $5, NOW(), NOW())
     ON CONFLICT (person_id, organization_id) WHERE closed_at IS NULL DO NOTHING`,
    [post[0].id, organizationId, personUuid(personId), startDate, endDate],
  );
}

async function seatPerson(client, ocdid, person) {
  const organizationId = await organizationFor(client, ocdid);
  // Fall back rather than fail: a fixture office that slugs to no seeded role would otherwise
  // break seeding on a foreign key, which reads as a schema fault rather than a fixture one.
  const wanted = roleSlug(person.office?.name);
  const { rows: role } = await client.query(`SELECT id FROM roles WHERE id = $1`, [
    wanted,
  ]);
  await seatAt(client, ocdid, {
    organizationId,
    personId: person.id,
    roleId: role.length ? wanted : SEAT_ROLE_FALLBACK,
    // The person's own ward when the fixture gave them one, else the jurisdiction itself.
    division: person.office?.division_ocdid ?? divisionOf(ocdid),
    startDate: person.start_date ?? null,
    endDate: person.end_date ?? null,
  });
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
  // Source records point at the organization (205: RESTRICT); reseeding the card writes them again.
  await client.query(`DELETE FROM source_records WHERE jurisdiction_ocdid = $1`, [ocdid]);
  await client.query(`DELETE FROM organizations WHERE jurisdiction_ocdid = $1`, [
    ocdid,
  ]);
  await client.query(`DELETE FROM divisions WHERE jurisdiction_ocdid = $1`, [ocdid]);
  await client.query(`DELETE FROM people WHERE jurisdiction_ocdid = $1`, [ocdid]);
}

/** Seat somebody in a *named* body, minting it if this jurisdiction has none by that name.
 *
 * `seatPerson` takes whichever organization the jurisdiction happens to have, which is all a
 * one-body fixture needs. Holding an office in two bodies is a different shape, and the
 * `(person_id, organization_id)` partial unique index is what makes it legal: one open
 * membership per body, several bodies per person.
 */
async function namedOrganization(client, ocdid, name) {
  const { rows } = await client.query(
    `INSERT INTO organizations (jurisdiction_ocdid, name) VALUES ($1, $2)
     ON CONFLICT (jurisdiction_ocdid, name) DO UPDATE SET name = EXCLUDED.name
     RETURNING id`,
    [ocdid, name],
  );
  return rows[0].id;
}

async function seatIn(client, ocdid, { organizationName, personId, roleId, division }) {
  await seatAt(client, ocdid, {
    organizationId: await namedOrganization(client, ocdid, organizationName),
    personId,
    roleId,
    division,
  });
}

/** The facts behind a published roster: a published changeset, and one sighting per person.
 *
 * Projection rows alone are no longer enough. Since the card's `existing` side became
 * `published_card_rows` it is derived from facts, and a roster seeded only into `people` and
 * `memberships` reads as an empty roster there — so every scraped person diffed as New, and
 * nobody could depart. The published changeset is the prior collection, which a review also
 * needs to render in RECONCILE mode, so this is one row rather than two.
 */
async function seedPublishedFacts(client, ocdid, people) {
  await seedPriorCollection(client, ocdid);
  const changesetId = priorCollectionId(ocdid);
  const organizationId = await organizationFor(client, ocdid);
  await client.query(`DELETE FROM source_records WHERE changeset_id = $1`, [changesetId]);
  for (const person of people) {
    const { rows } = await client.query(
      `INSERT INTO source_records (changeset_id, jurisdiction_ocdid, name, label, source_url,
                                   url, phone, email, image, start_date, end_date,
                                   organization_id, created_at)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12, NOW() - INTERVAL '30 days')
       RETURNING id`,
      [
        changesetId,
        ocdid,
        person.name,
        // The office as a page would have printed it, ward and all — `sightingLabel`, the same
        // rendering the proposed side uses. The office name alone derives a post in the
        // jurisdiction's own division, so every ward member would read as having moved.
        sightingLabel(person.office) || "Council Member",
        (person.source_urls ?? [])[0] ?? "https://example.gov/roster",
        (person.urls ?? [])[0] ?? null,
        (person.phones ?? [])[0] ?? null,
        (person.emails ?? [])[0] ?? null,
        person.image ?? null,
        person.start_date ?? null,
        person.end_date ?? null,
        organizationId,
      ],
    );
    await client.query(
      `INSERT INTO source_record_identities (source_record_id, person_id, resolved_at)
       VALUES ($1, $2, NOW() - INTERVAL '30 days')`,
      [rows[0].id, personUuid(person.id)],
    );
  }
}

/** A published roster: the facts it derives from, and the projection rows those facts produce.
 *
 * Both, because two readers disagree about where a published roster lives — the review card
 * derives it, the jurisdiction page reads the stored rows. Production keeps them in step by
 * folding; a fixture keeps them in step by writing the same office twice, which is why
 * `seatPerson` computes the post id the fold would.
 */
async function seedPublishedRoster(client, ocdid, people) {
  for (const person of people) {
    await seedPerson(client, ocdid, person);
  }
  await seedPublishedFacts(client, ocdid, people);
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

// An attempt still going: no `finished_at`, and no changeset yet. This is what disables a
// state's scrape button, and what the "already running" figure counts.
async function seedRunInFlight(client, id, ocdid) {
  await client.query(
    `INSERT INTO pipeline_runs (id, jurisdiction_ocdid, status, progress)
     VALUES ($1, $2, 'SCRAPE_PAGE', 40)
     ON CONFLICT (id) DO NOTHING`,
    [id, ocdid],
  );
}

// An attempt that died before ingest, so it left no changeset behind to be reviewed or
// dismissed. Windowed by `created_at`, hence the age.
async function seedFailedRun(client, id, ocdid, ageSeconds) {
  await client.query(
    `INSERT INTO pipeline_runs (id, jurisdiction_ocdid, status, progress,
                                created_at, updated_at, finished_at)
     VALUES ($1, $2, 'ERROR', 20,
             NOW() - ($3 * INTERVAL '1 second'),
             NOW() - ($3 * INTERVAL '1 second'),
             NOW() - ($3 * INTERVAL '1 second'))
     ON CONFLICT (id) DO NOTHING`,
    [id, ocdid, ageSeconds],
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
      `INSERT INTO users (provider, provider_user_id, email, username, role)
       VALUES ($1, $2, $3, $4, 'contributors')
       ON CONFLICT (provider, provider_user_id)
       DO UPDATE SET email = EXCLUDED.email, role = EXCLUDED.role`,
      [
        TEST_USER_PROVIDER,
        TEST_USER_PROVIDER_ID,
        "e2e@civicpatch.org",
        "e2e-test-user",
      ],
    );

    // Jurisdiction, with a prior collection so the review renders in RECONCILE mode
    // (old<->new diff panel). The baseline fixture below gets none.
    await client.query(
      `INSERT INTO jurisdictions (jurisdiction_ocdid, state, status, data)
       VALUES ($1, 'nj', 'active', '{"name":"E2E Test City","geoid":"0600001"}')
       ON CONFLICT (jurisdiction_ocdid)
       DO UPDATE SET state = EXCLUDED.state, data = EXCLUDED.data`,
      [TEST_JURISDICTION_OCDID],
    );
    await seedPriorCollection(client, TEST_JURISDICTION_OCDID);

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
    for (const [jOcdid, jName, reqId, prNum, stateCode, geoidPrefix] of [
      [
        TEST_JURISDICTION_OCDID_2,
        "E2E Test City 2",
        TEST_CHANGESET_ID_2,
        2,
        "nj",
        "060000",
      ],
      [
        TEST_JURISDICTION_OCDID_3,
        "E2E Test City 3",
        TEST_CHANGESET_ID_3,
        3,
        "nj",
        "060000",
      ],
      [
        TX_JURISDICTION_OCDID,
        "E2E TX City",
        TX_CHANGESET_ID,
        10,
        "tx",
        "480000",
      ],
    ]) {
      await client.query(
        `INSERT INTO jurisdictions (jurisdiction_ocdid, state, status, data)
         VALUES ($1, $3, 'active', $2)
         ON CONFLICT (jurisdiction_ocdid) DO UPDATE SET state = EXCLUDED.state, data = EXCLUDED.data`,
        [
          jOcdid,
          JSON.stringify({ name: jName, geoid: `${geoidPrefix}${prNum}` }),
          stateCode,
        ],
      );
      await seedPriorCollection(client, jOcdid);
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

    await seedRunInFlight(client, NJ_RUN_IN_FLIGHT_ID, TEST_JURISDICTION_OCDID);
    await seedFailedRun(
      client,
      NJ_RUN_FAILED_ID,
      TEST_JURISDICTION_OCDID_2,
      3600,
    );
    await seedFailedRun(client, TX_RUN_FAILED_ID, TX_JURISDICTION_OCDID, 7200);

    // Baseline card — no prior collection, deliberately, so the review is BASELINE mode.
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

    // Populated reconcile card — a prior collection → RECONCILE mode, with existing
    // people so the diff renders changed / added / removed states.
    await client.query(
      `INSERT INTO jurisdictions (jurisdiction_ocdid, state, status, data)
       VALUES ($1, 'nh', 'active', '{"name":"E2E Reconcile City","geoid":"3300001"}')
       ON CONFLICT (jurisdiction_ocdid)
       DO UPDATE SET state = EXCLUDED.state, data = EXCLUDED.data`,
      [RECONCILE_JURISDICTION_OCDID],
    );
    await seedPriorCollection(client, RECONCILE_JURISDICTION_OCDID);
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
    await seedPublishedRoster(client, RECONCILE_JURISDICTION_OCDID, reconcileExisting);
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
      `INSERT INTO jurisdictions (jurisdiction_ocdid, state, status, data)
       VALUES ($1, 'ma', 'active', '{"name":"E2E Scale City","geoid":"2500001"}')
       ON CONFLICT (jurisdiction_ocdid)
       DO UPDATE SET state = EXCLUDED.state, data = EXCLUDED.data`,
      [SCALE_JURISDICTION_OCDID],
    );
    await clearRoster(client, SCALE_JURISDICTION_OCDID);
    await seedPublishedRoster(client, SCALE_JURISDICTION_OCDID, buildScaleExisting());
    await seedReviewCard(client, {
      changesetId: SCALE_CHANGESET_ID,
      ocdid: SCALE_JURISDICTION_OCDID,
      people: asSightings(buildScaleProposed()),
    });

    // Issue-markers card — reconcile mode, all proposed render as added cards.
    await client.query(
      `INSERT INTO jurisdictions (jurisdiction_ocdid, state, status, data)
       VALUES ($1, 'me', 'active', '{"name":"E2E Markers City","geoid":"2300001"}')
       ON CONFLICT (jurisdiction_ocdid)
       DO UPDATE SET state = EXCLUDED.state, data = EXCLUDED.data`,
      [MARKERS_JURISDICTION_OCDID],
    );
    await seedPriorCollection(client, MARKERS_JURISDICTION_OCDID);
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
    await seedPublishedRoster(client, MARKERS_JURISDICTION_OCDID, markersPublished);
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

    // A published roster where one person sits in two bodies, for the jurisdiction page's
    // own editor. No changeset: this page edits live data, so the fixture is the roster.
    await client.query(
      `INSERT INTO jurisdictions (jurisdiction_ocdid, state, status, data)
       VALUES ($1, 'md', 'active', '{"name":"E2E Two Body City","geoid":"2400009"}')
       ON CONFLICT (jurisdiction_ocdid)
       DO UPDATE SET state = EXCLUDED.state, data = EXCLUDED.data`,
      [TWO_BODY_JURISDICTION_OCDID],
    );
    await clearRoster(client, TWO_BODY_JURISDICTION_OCDID);
    for (const person of [
      { id: "two-body-ada", name: "Ada Two-Body" },
      { id: "two-body-bo", name: "Bo Council-Only" },
    ]) {
      // `source_urls` is not decoration: the roster editor blocks Publish on it
      // (`blockingErrors`), so a person seeded without one can never be published.
      await client.query(
        `INSERT INTO people (id, jurisdiction_ocdid, name, source_urls, updated_at)
         VALUES ($1, $2, $3, $4, NOW())
         ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name,
                                        source_urls = EXCLUDED.source_urls`,
        [
          personUuid(person.id),
          TWO_BODY_JURISDICTION_OCDID,
          person.name,
          ["https://e2e-two-body.example.gov/roster"],
        ],
      );
    }
    const twoBodyDivision = divisionOf(TWO_BODY_JURISDICTION_OCDID);
    // Ada in both bodies, Bo in one: the second row is what proves a removal took only the
    // row it was pressed on.
    await seatIn(client, TWO_BODY_JURISDICTION_OCDID, {
      organizationName: TWO_BODY_COUNCIL,
      personId: "two-body-ada",
      roleId: "council-member",
      division: twoBodyDivision,
    });
    await seatIn(client, TWO_BODY_JURISDICTION_OCDID, {
      organizationName: TWO_BODY_SCHOOL_BOARD,
      personId: "two-body-ada",
      roleId: "trustee",
      division: twoBodyDivision,
    });
    await seatIn(client, TWO_BODY_JURISDICTION_OCDID, {
      organizationName: TWO_BODY_COUNCIL,
      personId: "two-body-bo",
      roleId: "council-member",
      division: twoBodyDivision,
    });

    // A scrape of both bodies in one changeset: Ada listed under each, Bo under the council
    // only. Source records name their own organization, so one changeset spans two.
    await client.query(
      `INSERT INTO jurisdictions (jurisdiction_ocdid, state, status, data)
       VALUES ($1, 'de', 'active', '{"name":"E2E Two Org City","geoid":"1000010"}')
       ON CONFLICT (jurisdiction_ocdid)
       DO UPDATE SET state = EXCLUDED.state, data = EXCLUDED.data`,
      [TWO_ORG_JURISDICTION_OCDID],
    );
    await clearRoster(client, TWO_ORG_JURISDICTION_OCDID);
    await seedPublishedRoster(client, TWO_ORG_JURISDICTION_OCDID, [
      {
        id: "two-org-ada",
        name: "Ada Two-Body",
        office: { name: "Council Member" },
        source_urls: ["https://e2e-two-org.example.gov/council"],
      },
    ]);
    await seedReviewCard(client, {
      changesetId: TWO_ORG_CHANGESET_ID,
      ocdid: TWO_ORG_JURISDICTION_OCDID,
      people: [
        {
          person_id: "two-org-ada",
          name: "Ada Two-Body",
          label: "Council Member",
          organization: TWO_BODY_COUNCIL,
        },
        {
          person_id: "two-org-ada",
          name: "Ada Two-Body",
          label: "Trustee",
          organization: TWO_BODY_SCHOOL_BOARD,
        },
      ],
    });

    // Read-only card — merged PR, so the card renders in its terminal state.
    // `url` on the jurisdiction data is what surfaces as the website link.
    await client.query(
      `INSERT INTO jurisdictions (jurisdiction_ocdid, state, status, data)
       VALUES ($1, 'ri', 'active', $2)
       ON CONFLICT (jurisdiction_ocdid)
       DO UPDATE SET state = EXCLUDED.state, data = EXCLUDED.data`,
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

    // One row per section of the issues page. Both cascade with their parent, so teardown
    // does not name them.
    await client.query(
      `INSERT INTO pipeline_run_issues (pipeline_run_id, issue_type, data, status)
       VALUES ($1, 'pipeline_error', $2, 'pending')
       ON CONFLICT (pipeline_run_id, issue_type) DO UPDATE
         SET data = EXCLUDED.data, status = EXCLUDED.status, resolved_at = NULL`,
      [NJ_RUN_FAILED_ID, JSON.stringify({ error: "Navigation timed out" })],
    );

    await client.query(
      `INSERT INTO changeset_issues (changeset_id, issue_type, data, status)
       SELECT $1, 'user_reported', $2, 'pending'
       WHERE NOT EXISTS (
         SELECT 1 FROM changeset_issues WHERE changeset_id = $1 AND issue_type = 'user_reported'
       )`,
      [
        // Against the prior collection, not the card under review: an open user report holds
        // its changeset out of `AVAILABLE_FOR_REVIEW`, and putting one on TEST_CHANGESET_ID
        // took the first card away from every review spec.
        priorCollectionId(TEST_JURISDICTION_OCDID),
        JSON.stringify({
          title: "Jane Smith is no longer on the council",
          body: "She resigned in March; the city page is stale.",
          github_issue_url: "",
          github_issue_number: 0,
          reported_by_user_id: "e2e",
        }),
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
    // No FK from `pipeline_runs` to `jurisdictions`, so these outlive their jurisdiction
    // unless dropped by hand.
    await client.query(`DELETE FROM pipeline_runs WHERE id = ANY($1)`, [
      SEEDED_RUN_IDS,
    ]);
    // By jurisdiction, not by changeset id: the card under review is no longer the only
    // changeset a fixture seeds — `seedPriorCollection` adds one to put the review in
    // RECONCILE mode.
    for (const jOcdid of [
      TEST_JURISDICTION_OCDID,
      TEST_JURISDICTION_OCDID_2,
      TEST_JURISDICTION_OCDID_3,
      BASELINE_JURISDICTION_OCDID,
      RECONCILE_JURISDICTION_OCDID,
      SCALE_JURISDICTION_OCDID,
      TX_JURISDICTION_OCDID,
      MARKERS_JURISDICTION_OCDID,
      READ_ONLY_JURISDICTION_OCDID,
      TWO_BODY_JURISDICTION_OCDID,
      TWO_ORG_JURISDICTION_OCDID,
    ]) {
      // source_records cascades from changesets; identities cascade from source_records.
      await client.query(`DELETE FROM changesets WHERE jurisdiction_ocdid = $1`, [jOcdid]);
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
    // Claims outlive the jurisdictions they are about: `assertions.created_by` is NOT NULL and
    // points at the user, so deleting the test user first fails on the foreign key. Every edit
    // a spec makes files one now, which is why this was not needed before the edit route.
    await client.query(
      `DELETE FROM assertions WHERE created_by IN (
         SELECT id FROM users WHERE provider = $1
       )`,
      [TEST_USER_PROVIDER],
    );
    await client.query(
      `DELETE FROM users WHERE provider = $1 AND provider_user_id = $2`,
      [TEST_USER_PROVIDER, TEST_USER_PROVIDER_ID],
    );
  } finally {
    await client.end();
  }
}
