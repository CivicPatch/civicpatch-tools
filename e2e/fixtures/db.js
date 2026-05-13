import pg from "pg";

const { Client } = pg;

// Fixed IDs so teardown can target them precisely
const TEST_USER_PROVIDER = "github";
const TEST_USER_PROVIDER_ID = "test-user-e2e";
export const TEST_JURISDICTION_OCDID =
  "ocd-jurisdiction/country:us/state:nj/place:e2e_test/government";
export const TEST_REQUEST_ID = "00000000-0000-0000-eeee-000000000001";
const TEST_PR_ID = "00000000-0000-0000-eeee-000000000002";

export const TEST_JURISDICTION_OCDID_2 =
  "ocd-jurisdiction/country:us/state:nj/place:e2e_test_2/government";
export const TEST_REQUEST_ID_2 = "00000000-0000-0000-eeee-000000000003";
const TEST_PR_ID_2 = "00000000-0000-0000-eeee-000000000004";

export const TEST_JURISDICTION_OCDID_3 =
  "ocd-jurisdiction/country:us/state:nj/place:e2e_test_3/government";
export const TEST_REQUEST_ID_3 = "00000000-0000-0000-eeee-000000000005";
const TEST_PR_ID_3 = "00000000-0000-0000-eeee-000000000006";

// Map fixtures — one jurisdiction per status bucket so map e2e tests can assert
// fresh/stale/gap/untracked colors deterministically against known OCD IDs.
export const MAP_FIXTURES = {
  fresh:     "ocd-jurisdiction/country:us/state:nj/place:e2e_map_fresh/government",
  stale:     "ocd-jurisdiction/country:us/state:nj/place:e2e_map_stale/government",
  gap:       "ocd-jurisdiction/country:us/state:nj/place:e2e_map_gap/government",
  untracked: "ocd-jurisdiction/country:us/state:nj/place:e2e_map_untracked/government",
};

function makeClient() {
  return new Client({
    connectionString:
      process.env.E2E_DB_URL ??
      "postgres://e2e:e2e_password@localhost:8101/e2e_db",
  });
}

export async function seedE2eFixtures() {
  const client = makeClient();
  await client.connect();
  try {
    // User
    await client.query(
      `INSERT INTO users (provider, provider_user_id, email, display_name)
       VALUES ($1, $2, $3, $4)
       ON CONFLICT (provider, provider_user_id)
       DO UPDATE SET email = EXCLUDED.email`,
      [TEST_USER_PROVIDER, TEST_USER_PROVIDER_ID, "e2e@civicpatch.org", "E2E Test User"]
    );

    // Role — required for TEAM_REQUIRED routes with Role.DEFAULT
    await client.query(
      `INSERT INTO user_roles (provider, provider_user_id, role)
       VALUES ($1, $2, 'default')
       ON CONFLICT (provider, provider_user_id, role) DO NOTHING`,
      [TEST_USER_PROVIDER, TEST_USER_PROVIDER_ID]
    );

    // Jurisdiction
    await client.query(
      `INSERT INTO jurisdictions (jurisdiction_ocdid, state, status, data)
       VALUES ($1, 'nj', 'current', '{"name":"E2E Test City","geoid":"0600001"}')
       ON CONFLICT (jurisdiction_ocdid)
       DO UPDATE SET state = EXCLUDED.state, data = EXCLUDED.data`,
      [TEST_JURISDICTION_OCDID]
    );

    // Request with proposed people (data_json) and one issue (review_json)
    // data_json populated so the navigate endpoint skips the GitHub YAML fetch
    await client.query(
      `INSERT INTO requests (id, request_type, jurisdiction_ocdid, arguments_json, data_json, review_json, created_at, updated_at)
       VALUES ($1, 'people_collection', $2, '{}',
               '[{"name":"Jane Smith","roles":[{"title":"Council Member"}]}]',
               '{"issues":[{"type":"missing_email","key":"jane-smith"}]}',
               NOW(), NOW())
       ON CONFLICT (id) DO UPDATE SET data_json = EXCLUDED.data_json`,
      [TEST_REQUEST_ID, TEST_JURISDICTION_OCDID]
    );

    // pipeline_runs row required for get_pipeline_run_data_json
    await client.query(
      `INSERT INTO pipeline_runs (request_id, status, progress, created_at, updated_at)
       VALUES ($1, 'success', 100, NOW(), NOW())
       ON CONFLICT DO NOTHING`,
      [TEST_REQUEST_ID]
    );

    // Pull request — status='open' makes the card appear in the review queue
    // url=NULL so sync_single_pr_state exits early (no GitHub call)
    await client.query(
      `INSERT INTO pull_requests (id, request_id, pr_number, url, status, created_at, updated_at)
       VALUES ($1, $2, 0, NULL, 'open', NOW(), NOW())
       ON CONFLICT (request_id) DO NOTHING`,
      [TEST_PR_ID, TEST_REQUEST_ID]
    );

    // Second card
    for (const [jOcdid, jName, reqId, prId, prNum] of [
      [TEST_JURISDICTION_OCDID_2, "E2E Test City 2", TEST_REQUEST_ID_2, TEST_PR_ID_2, 2],
      [TEST_JURISDICTION_OCDID_3, "E2E Test City 3", TEST_REQUEST_ID_3, TEST_PR_ID_3, 3],
    ]) {
      await client.query(
        `INSERT INTO jurisdictions (jurisdiction_ocdid, state, status, data)
         VALUES ($1, 'nj', 'current', $2)
         ON CONFLICT (jurisdiction_ocdid) DO UPDATE SET state = EXCLUDED.state, data = EXCLUDED.data`,
        [jOcdid, JSON.stringify({ name: jName, geoid: `060000${prNum}` })]
      );
      await client.query(
        `INSERT INTO requests (id, request_type, jurisdiction_ocdid, arguments_json, data_json, review_json, created_at, updated_at)
         VALUES ($1, 'people_collection', $2, '{}', '[]', '{}', NOW(), NOW())
         ON CONFLICT (id) DO NOTHING`,
        [reqId, jOcdid]
      );
      await client.query(
        `INSERT INTO pipeline_runs (request_id, status, progress, created_at, updated_at)
         VALUES ($1, 'success', 100, NOW(), NOW())
         ON CONFLICT DO NOTHING`,
        [reqId]
      );
      await client.query(
        `INSERT INTO pull_requests (id, request_id, pr_number, url, status, created_at, updated_at)
         VALUES ($1, $2, $3, NULL, 'open', NOW(), NOW())
         ON CONFLICT (request_id) DO NOTHING`,
        [prId, reqId, prNum]
      );
    }

    // Map status fixtures — one per bucket (fresh / stale / gap / untracked).
    // The presence of a `url` and a `people` row drives the status the map paints.
    const STALE_DAYS = 200;  // > FRESH_THRESHOLD_DAYS (90)
    for (const [ocdid, name, hasUrl, peopleAgeDays] of [
      [MAP_FIXTURES.fresh,     "E2E Map Fresh",     true,  0],
      [MAP_FIXTURES.stale,     "E2E Map Stale",     true,  STALE_DAYS],
      [MAP_FIXTURES.gap,       "E2E Map Gap",       true,  null],
      [MAP_FIXTURES.untracked, "E2E Map Untracked", false, null],
    ]) {
      const data = hasUrl
        ? { name, url: `https://example.test/${name.replace(/\s+/g, "-").toLowerCase()}` }
        : { name };
      await client.query(
        `INSERT INTO jurisdictions (jurisdiction_ocdid, state, status, data)
         VALUES ($1, 'nj', 'current', $2)
         ON CONFLICT (jurisdiction_ocdid) DO UPDATE SET state = EXCLUDED.state, data = EXCLUDED.data`,
        [ocdid, JSON.stringify(data)]
      );
      if (peopleAgeDays !== null) {
        await client.query(
          `INSERT INTO people (jurisdiction_ocdid, data, status, updated_at)
           VALUES ($1, '{"name":"E2E Person"}', 'current', NOW() - ($2 || ' days')::interval)`,
          [ocdid, peopleAgeDays]
        );
      }
    }
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
      [TEST_USER_PROVIDER, TEST_USER_PROVIDER_ID]
    );
    await client.query(
      `DELETE FROM review_sessions WHERE user_id = (
         SELECT id FROM users WHERE provider = $1 AND provider_user_id = $2
       )`,
      [TEST_USER_PROVIDER, TEST_USER_PROVIDER_ID]
    );
    for (const [prId, reqId, jOcdid] of [
      [TEST_PR_ID, TEST_REQUEST_ID, TEST_JURISDICTION_OCDID],
      [TEST_PR_ID_2, TEST_REQUEST_ID_2, TEST_JURISDICTION_OCDID_2],
      [TEST_PR_ID_3, TEST_REQUEST_ID_3, TEST_JURISDICTION_OCDID_3],
    ]) {
      await client.query(`DELETE FROM pull_requests WHERE id = $1`, [prId]);
      await client.query(`DELETE FROM pipeline_runs WHERE request_id = $1`, [reqId]);
      await client.query(`DELETE FROM requests WHERE id = $1`, [reqId]);
      await client.query(`DELETE FROM jurisdictions WHERE jurisdiction_ocdid = $1`, [jOcdid]);
    }
    for (const ocdid of Object.values(MAP_FIXTURES)) {
      await client.query(`DELETE FROM people WHERE jurisdiction_ocdid = $1`, [ocdid]);
      await client.query(`DELETE FROM jurisdictions WHERE jurisdiction_ocdid = $1`, [ocdid]);
    }
    await client.query(
      `DELETE FROM user_roles WHERE provider = $1 AND provider_user_id = $2`,
      [TEST_USER_PROVIDER, TEST_USER_PROVIDER_ID]
    );
    await client.query(
      `DELETE FROM users WHERE provider = $1 AND provider_user_id = $2`,
      [TEST_USER_PROVIDER, TEST_USER_PROVIDER_ID]
    );
  } finally {
    await client.end();
  }
}
