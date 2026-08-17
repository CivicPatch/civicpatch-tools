import { config } from "./assets/config.js";
import { parseSaveError } from "./api-errors.js";

const API_URL = config.apiUrl;

function getCsrfCookie() {
  const name = "csrf_token=";
  const parts = document.cookie.split(";");
  for (let i = 0; i < parts.length; i++) {
    let c = parts[i].trim();
    if (c.indexOf(name) === 0)
      return decodeURIComponent(c.substring(name.length));
  }
  return "";
}

export const fetchPullRequests = async (jurisdictionOcdid) => {
  const params = new URLSearchParams({ jurisdiction_ocdid: jurisdictionOcdid });
  const res = await fetch(`${API_URL}/api/v1/pull_requests/with-data?${params}`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const fetchIssueCounts = async (stateCode) => {
  const params = new URLSearchParams();
  if (stateCode) params.set("state_code", stateCode);
  const query = params.toString() ? `?${params}` : "";
  const res = await fetch(`${API_URL}/api/v1/pipeline_runs/issues/counts${query}`, { credentials: "include" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const fetchChangeLogs = async (bucket, page = 1, perPage = 20) => {
  const params = new URLSearchParams({ bucket, page, per_page: perPage });
  const res = await fetch(`${API_URL}/api/v1/change_logs?${params}`, { credentials: "include" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const fetchJobIssues = async (tags, page, perPage, sort, stateCode, showArchived = false) => {
  const params = new URLSearchParams({ page, per_page: perPage, sort });
  if (tags && tags.length) params.set("tags", tags.join(","));
  if (stateCode) params.set("state_code", stateCode);
  if (showArchived) params.set("show_archived", "true");
  const res = await fetch(`${API_URL}/api/v1/pipeline_runs/issues?${params}`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const fetchIssueDetails = async (issueId) => {
  const res = await fetch(`${API_URL}/api/v1/pipeline_runs/issues/${issueId}/details`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const flagIssue = async (issueId, is_flagged) => {
  const res = await fetch(`${API_URL}/api/v1/pipeline_runs/issues/${issueId}/flag`, {
    credentials: "include",
    method: "PATCH",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": getCsrfCookie() },
    body: JSON.stringify({ is_flagged }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const dismissIssue = async (issueId) => {
  const res = await fetch(`${API_URL}/api/v1/pipeline_runs/issues/${issueId}/dismiss`, {
    credentials: "include",
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": getCsrfCookie() },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const resolveReviewIssue = async (issueId, body = {}) => {
  const res = await fetch(`${API_URL}/api/v1/pipeline_runs/issues/${issueId}/resolve`, {
    credentials: "include",
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": getCsrfCookie() },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const fetchPullRequestsWithData = async (stateCode, page = 1, perPage = 10, view = "quick") => {
  const params = new URLSearchParams();
  if (stateCode) params.set("state_code", stateCode);
  params.set("page", page);
  params.set("per_page", perPage);
  params.set("view", view);
  const res = await fetch(`${API_URL}/api/v1/pull_requests/with-data?${params}`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

// The catchable, synchronous half of publishing: validate + write the file +
// enqueue the merge. Returns once the server accepts the request (202); throws
// (with a parsed message) on a validation/save rejection.
export const saveAndEnqueueMerge = async (pullRequestNumber, request_id, jurisdiction_ocdid, people) => {
  const res = await fetch(`${API_URL}/api/v1/pull_requests/${pullRequestNumber}/save-and-merge`, {
    credentials: "include",
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": getCsrfCookie(),
    },
    body: JSON.stringify({ request_id, jurisdiction_ocdid, ...(people ? { data: people } : {}) }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const err = new Error(parseSaveError(body, res.status));
    err.status = res.status;
    throw err;
  }
  return res.json();
};

// Commit the reviewer's edits to the job branch without publishing. The PR stays
// in the review pool; the session entry is held until the session is released.
// Throws (with a parsed message) on a validation/save rejection, like the above.
export const saveReviewData = async (pullRequestNumber, request_id, jurisdiction_ocdid, people) => {
  const res = await fetch(`${API_URL}/api/v1/pull_requests/${pullRequestNumber}/save`, {
    credentials: "include",
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": getCsrfCookie(),
    },
    body: JSON.stringify({ request_id, jurisdiction_ocdid, data: people }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const err = new Error(parseSaveError(body, res.status));
    err.status = res.status;
    throw err;
  }
  return res.json();
};

// The background half: poll until the async merge settles. Resolves on success,
// throws on a merge error or timeout.
export const pollMergeStatus = async (pullRequestNumber) => {
  const POLL_INTERVAL_MS = 2000;
  const MAX_ATTEMPTS = 120;
  for (let i = 0; i < MAX_ATTEMPTS; i++) {
    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
    const statusRes = await fetch(`${API_URL}/api/v1/pull_requests/${pullRequestNumber}/merge-status`, {
      credentials: "include",
    });
    if (!statusRes.ok) {
      const body = await statusRes.json().catch(() => ({}));
      throw new Error(body.error || `HTTP ${statusRes.status}`);
    }
    const { status, error } = await statusRes.json();
    if (status === "merged") return { status: "success" };
    if (status === "error") throw new Error(error || "Merge failed");
  }
  throw new Error("Merge timed out");
};

export const searchPeople = async (jurisdictionOcdid, name) => {
  const params = new URLSearchParams({ jurisdiction_ocdid: jurisdictionOcdid, name });
  const res = await fetch(`${API_URL}/api/v1/people/search?${params}`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const batchResolvePeople = async (jurisdictionOcdid, people) => {
  const res = await fetch(`${API_URL}/api/v1/people/batch-resolve`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": getCsrfCookie(),
    },
    body: JSON.stringify({
      jurisdiction_ocdid: jurisdictionOcdid,
      people: people.map(p => ({ id: p.id, name: p.name, email: p.emails?.[0] ?? null })),
      with_data: true,
    }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const fetchPullRequestData = async (jurisdictionOcdid, requestId) => {
  const params = new URLSearchParams({
    jurisdiction_ocdid: jurisdictionOcdid,
    request_id: requestId,
  });
  const res = await fetch(`${API_URL}/api/v1/pull_requests/data?${params}`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const fetchRoles = async () => {
  const res = await fetch(`${API_URL}/api/v1/roles`, { credentials: "include" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const putRoles = async (body) => {
  const res = await fetch(`${API_URL}/api/v1/roles`, {
    method: "PUT",
    credentials: "include",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": getCsrfCookie() },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const reorderRoles = async ({ roleOrder, movedRoles }) => {
  const res = await fetch(`${API_URL}/api/v1/roles/reorder`, {
    method: "PUT",
    credentials: "include",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": getCsrfCookie() },
    body: JSON.stringify({ role_order: roleOrder, moved_roles: movedRoles }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const deleteRole = async (roleId) => {
  const res = await fetch(`${API_URL}/api/v1/roles/${encodeURIComponent(roleId)}`, {
    method: "DELETE",
    credentials: "include",
    headers: { "X-CSRF-Token": getCsrfCookie() },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const fetchJurisdictionHistory = async (jurisdictionOcdid) => {
  const params = new URLSearchParams({ jurisdiction_ocdid: jurisdictionOcdid });
  const res = await fetch(`/api/v1/jurisdictions/history?${params}`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const generatePersonId = async () => {
  const res = await fetch(`${API_URL}/api/v1/people/generate-id`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": getCsrfCookie(),
    },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  return data.data.person_id;
};

export const fetchReview = async (requestId) => {
  const res = await fetch(`${API_URL}/api/v1/pull_requests/${requestId}/review`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const fetchReportedIssues = async (requestId) => {
  const res = await fetch(`${API_URL}/api/v1/pull_requests/${requestId}/issues`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const reportReviewIssue = async (requestId, description) => {
  const res = await fetch(`${API_URL}/api/v1/pull_requests/${requestId}/issues`, {
    credentials: "include",
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": getCsrfCookie() },
    body: JSON.stringify({ description }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const closePullRequest = async (request_id, pullRequestNumber) => {
  const res = await fetch(`${API_URL}/api/v1/pull_requests/${pullRequestNumber}?request_id=${request_id}`, {
    credentials: "include",
    method: "DELETE",
    headers: {
      "X-CSRF-Token": getCsrfCookie(),
    },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const fetchPeopleDirectory = async (jurisdictionOcdid, page = 1, perPage = 20) => {
  const params = new URLSearchParams({ jurisdiction_ocdid: jurisdictionOcdid, page, per_page: perPage });
  const res = await fetch(`${API_URL}/api/v1/people/directory?${params}`, { credentials: "include" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const patchPeopleData = async (jurisdictionOcdid, data) => {
  const res = await fetch(`${API_URL}/api/v1/people/data`, {
    method: "PATCH",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": getCsrfCookie(),
    },
    body: JSON.stringify({ jurisdiction_ocdid: jurisdictionOcdid, data }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(parseSaveError(body, res.status));
  }
  return res.json();
};

export const patchJurisdictionData = async (jurisdictionOcdid, data) => {
  const res = await fetch(`${API_URL}/api/v1/jurisdictions/data`, {
    method: "PATCH",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": getCsrfCookie(),
    },
    body: JSON.stringify({
      jurisdiction_ocdid: jurisdictionOcdid,
      url: data.url ?? null,
      geoid: data.geoid ?? null,
      population: data.population ? Number(data.population) : null,
    }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || `HTTP ${res.status}`);
  }
  return res.json();
};

export const fetchPeople = async (jurisdictionOcdid) => {
  const params = new URLSearchParams({ jurisdiction_ocdid: jurisdictionOcdid });
  const res = await fetch(`/api/v1/people?${params}`, { credentials: "include" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const fetchJurisdictionsByOcdids = async (ocdids) => {
  const res = await fetch(`/api/v1/jurisdictions/by-ocdids`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ocdids }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const fetchDashboard = async () => {
  const res = await fetch(`${API_URL}/api/v1/data/dashboard`, { credentials: "include" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const fetchMapsCoverage = async () => {
  const res = await fetch(`${API_URL}/api/v1/coverage`, { credentials: "include" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const fetchLocalStatus = async (state) => {
  const res = await fetch(`${API_URL}/api/v1/coverage/${state}/local`, { credentials: "include" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const fetchStateCoverageSummary = async (state) => {
  const res = await fetch(`${API_URL}/api/v1/coverage/${state}/summary`, { credentials: "include" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const fetchMunicipalityList = async (state) => {
  const res = await fetch(`${API_URL}/api/v1/coverage/${state}/municipalities`, { credentials: "include" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const fetchLeaderboard = async () => {
  const res = await fetch(`${API_URL}/api/v1/leaderboard`, { credentials: "include" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

/** Pipeline runs */
export const triggerPipelineRun = async (mode, jurisdictionOcdid, name, url, sourceUrls) => {
  const res = await fetch(`${API_URL}/api/v1/pipeline_runs`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": getCsrfCookie(),
    },
    body: JSON.stringify({
      dispatch_mode: mode,
      jurisdiction_ocdid: jurisdictionOcdid,
      name,
      url,
      ...(sourceUrls?.length ? { source_urls: sourceUrls } : {}),
    }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || `HTTP ${res.status}`);
  }
  return res.json();
};

export const fetchActivePipelineRuns = async (stateCode, page = 1, perPage = 25) => {
  const params = new URLSearchParams({ page, per_page: perPage });
  if (stateCode) params.set("state_code", stateCode);
  const res = await fetch(`${API_URL}/api/v1/pipeline_runs/active?${params}`, { credentials: "include" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const cancelPipelineRun = async (requestId) => {
  const res = await fetch(`${API_URL}/api/v1/pipeline_runs/${requestId}/cancel`, {
    method: "POST",
    credentials: "include",
    headers: { "X-CSRF-Token": getCsrfCookie() },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};


export const fetchJurisdictionsGeojson = async (lat, lng, zoom) => {
  const params = new URLSearchParams({ lat, long: lng, zoom });
  const res = await fetch(`/api/v1/jurisdictions/geojson?${params}`, { credentials: "include" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const fetchReviewStats = async (stateCode) => {
  const params = new URLSearchParams({ state_code: stateCode });
  const res = await fetch(`${API_URL}/api/v1/review-sessions/stats?${params}`, { credentials: "include" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const fetchActiveReviewSession = async (stateCode) => {
  const res = await fetch(
    `${API_URL}/api/v1/review-sessions/active?state_code=${encodeURIComponent(stateCode)}`,
    { credentials: "include" },
  );
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const createReviewSession = async (stateCode, dailyGoal) => {
  const res = await fetch(`${API_URL}/api/v1/review-sessions`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": getCsrfCookie() },
    body: JSON.stringify({ state_code: stateCode, daily_goal: dailyGoal }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const navigateToEntry = async (sessionId, entryNumber) => {
  const res = await fetch(`${API_URL}/api/v1/review-sessions/${sessionId}/navigate`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": getCsrfCookie() },
    body: JSON.stringify({ entry_number: entryNumber }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};


export const endReviewSession = async (sessionId) => {
  const res = await fetch(`${API_URL}/api/v1/review-sessions/${sessionId}/end`, {
    method: "POST",
    credentials: "include",
    headers: { "X-CSRF-Token": getCsrfCookie() },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const fetchSummary = async (stateCode) => {
  const params = new URLSearchParams();
  if (stateCode) params.set("state_code", stateCode);
  const query = params.toString() ? `?${params}` : "";
  const res = await fetch(`${API_URL}/api/v1/summary${query}`, { credentials: "include" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const fetchJurisdictionForState = async (stateCode) => {
  const params = new URLSearchParams({ limit: 1, state: stateCode });
  const res = await fetch(`${API_URL}/api/v1/jurisdictions/search?${params}`, { credentials: "include" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const fetchAllJurisdictionsForState = async (stateCode) => {
  const params = new URLSearchParams({ state: stateCode });
  const res = await fetch(`${API_URL}/api/v1/jurisdictions/search?${params}`, { credentials: "include" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const fetchPullRequestByRequestId = async (requestId) => {
  const res = await fetch(`${API_URL}/api/v1/pull_requests/by-request/${requestId}`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const fetchAdminUsers = async () => {
  const res = await fetch(`${API_URL}/api/admin/users`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const setUserRole = async (userId, role) => {
  const res = await fetch(`${API_URL}/api/admin/users/${userId}/role`, {
    credentials: "include",
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": getCsrfCookie(),
    },
    body: JSON.stringify({ role }),
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`HTTP ${res.status}: ${body}`);
  }
  return res.json();
};

export const inviteUser = async (email) => {
  const res = await fetch(`${API_URL}/api/admin/users/invite`, {
    credentials: "include",
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": getCsrfCookie(),
    },
    body: JSON.stringify({ email }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const err = new Error(body.detail || `HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
};

export const fetchPendingInvites = async () => {
  const res = await fetch(`${API_URL}/api/admin/users/pending`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const resendInvite = async (userId) => {
  const res = await fetch(`${API_URL}/api/admin/users/${userId}/resend-invite`, {
    credentials: "include",
    method: "POST",
    headers: { "X-CSRF-Token": getCsrfCookie() },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json();
};

export const revokeInvite = async (userId) => {
  const res = await fetch(`${API_URL}/api/admin/users/${userId}/invite`, {
    credentials: "include",
    method: "DELETE",
    headers: { "X-CSRF-Token": getCsrfCookie() },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json();
};

export const fetchDisplayNameSuggestion = async () => {
  const res = await fetch(`${API_URL}/api/internal/user/display-name/suggestion`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const body = await res.json();
  return body.data;
};

export const setDisplayName = async (displayName) => {
  const res = await fetch(`${API_URL}/api/internal/user/display-name`, {
    credentials: "include",
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": getCsrfCookie(),
    },
    body: JSON.stringify({ display_name: displayName }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const err = new Error(body.detail || `HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
};



// Nationwide jurisdiction typeahead. Each call aborts the previous one: with a debounce
// plus variable latency, a slow response for "sea" can otherwise land after "seattle"
// and overwrite it with stale results.
let jurisdictionSearchController = null;

/**
 * @param {string} query
 * @param {{ page?: number; limit?: number; state?: string; level?: string }} [opts]
 */
export const searchJurisdictions = async (query, { page = 1, limit = 10, state, level } = {}) => {
  jurisdictionSearchController?.abort();
  jurisdictionSearchController = new AbortController();

  const params = new URLSearchParams({ q: query, page, limit });
  if (state) params.set("state", state);
  if (level) params.set("level", level);
  const res = await fetch(`${API_URL}/api/v1/jurisdictions/search?${params}`, {
    credentials: "include",
    signal: jurisdictionSearchController.signal,
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

// One jurisdiction's open-data fields plus its scraped_at freshness stamp.
export const fetchJurisdiction = async (jurisdictionOcdid) => {
  const params = new URLSearchParams({ jurisdiction_ocdid: jurisdictionOcdid });
  const res = await fetch(`${API_URL}/api/v1/jurisdictions?${params}`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};
