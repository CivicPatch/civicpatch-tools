import pg from "pg";

const { Client } = pg;

// Fixed IDs so teardown can target them precisely
const TEST_USER_PROVIDER = "github";
const TEST_USER_PROVIDER_ID = "test-user-e2e";
export const TEST_JURISDICTION_OCDID =
  "ocd-jurisdiction/country:us/state:ca/place:e2e_test/government";
export const TEST_REQUEST_ID = "00000000-0000-0000-eeee-000000000001";
const TEST_PR_ID = "00000000-0000-0000-eeee-000000000002";

function makeClient() {
  return new Client({
    connectionString:
      process.env.E2E_DB_URL ??
      "postgres://civicpatch:development_password@localhost:6000/development_db",
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
      `INSERT INTO jurisdictions (jurisdiction_ocdid, status, data)
       VALUES ($1, 'active', '{"name":"E2E Test City","geoid":"0600001"}')
       ON CONFLICT (jurisdiction_ocdid)
       DO UPDATE SET data = EXCLUDED.data`,
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

    // Job — required for get_job_data_json join
    await client.query(
      `INSERT INTO jobs (request_id, status, created_at, updated_at)
       VALUES ($1, 'complete', NOW(), NOW())
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
    await client.query(
      `DELETE FROM pull_requests WHERE id = $1`,
      [TEST_PR_ID]
    );
    await client.query(`DELETE FROM jobs WHERE request_id = $1`, [TEST_REQUEST_ID]);
    await client.query(`DELETE FROM requests WHERE id = $1`, [TEST_REQUEST_ID]);
    await client.query(
      `DELETE FROM jurisdictions WHERE jurisdiction_ocdid = $1`,
      [TEST_JURISDICTION_OCDID]
    );
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
