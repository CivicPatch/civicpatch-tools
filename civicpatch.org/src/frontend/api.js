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
  const res = await fetch(`${API_URL}/api/v1/reviews/with-data?${params}`, {
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
  const res = await fetch(`${API_URL}/api/v1/reviews/with-data?${params}`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

// Publishing, start to finish: a 200 means the roster is live and stamped. Throws (with a
// parsed message) on a validation or publish rejection.
export const publishReview = async (changeset_id, jurisdiction_ocdid, people) => {
  const res = await fetch(`${API_URL}/api/v1/reviews/${changeset_id}/publish`, {
    credentials: "include",
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": getCsrfCookie(),
    },
    body: JSON.stringify({ changeset_id, jurisdiction_ocdid, ...(people ? { data: people } : {}) }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const err = new Error(parseSaveError(body, res.status));
    err.status = res.status;
    throw err;
  }
  return res.json();
};

// Commit the reviewer's edits to `data_json` without publishing. The request stays in the
// review pool; the session entry is held until the session is released.
export const saveReviewData = async (changeset_id, jurisdiction_ocdid, people) => {
  const res = await fetch(`${API_URL}/api/v1/reviews/${changeset_id}/save`, {
    credentials: "include",
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": getCsrfCookie(),
    },
    body: JSON.stringify({ changeset_id, jurisdiction_ocdid, data: people }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const err = new Error(parseSaveError(body, res.status));
    err.status = res.status;
    throw err;
  }
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

export const fetchPullRequestData = async (jurisdictionOcdid, changesetId) => {
  const params = new URLSearchParams({
    jurisdiction_ocdid: jurisdictionOcdid,
    changeset_id: changesetId,
  });
  const res = await fetch(`${API_URL}/api/v1/reviews/data?${params}`, {
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

// Undated: a post is not a temporal fact. Who holds one at a given moment is
// `fetchMemberships`, which windows on when a membership opened and closed.
export const fetchPosts = async (jurisdictionOcdid) => {
  const res = await fetch(`${API_URL}/api/v1/posts/${jurisdictionOcdid}`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const fetchMemberships = async (jurisdictionOcdid, asOf = null) => {
  const query = asOf ? `?as_of=${asOf}` : "";
  const res = await fetch(`${API_URL}/api/v1/memberships/${jurisdictionOcdid}${query}`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

// PUT, not POST: assigning is idempotent — re-assigning to the post someone already holds
// only sets the label. The response carries a `change` — `post_id` with a `before` when they
// moved — so the caller can say "moved from X" rather than "assigned".
export const assignMembership = async (personId, postId, label = null) => {
  const res = await fetch(`${API_URL}/api/v1/memberships`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ person_id: personId, post_id: postId, label }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const createPost = async (jurisdictionOcdid, body) => {
  const res = await fetch(`${API_URL}/api/v1/posts/${jurisdictionOcdid}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": getCsrfCookie() },
    body: JSON.stringify(body),
  });
  if (res.status === 409) throw new Error("That role and division already has a post.");
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const updatePost = async (postId, { headcount, isTracked }) => {
  const res = await fetch(`${API_URL}/api/v1/posts/${postId}`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": getCsrfCookie() },
    // `_is_tracked` is underscored on the wire: a post is a civic-data object and no
    // standard models tracking, so a consumer dropping every `_*` key still has a conforming
    // record. The route requires it — omitting it would silently re-track the post.
    body: JSON.stringify({
      _headcount: headcount,
      _is_tracked: isTracked,
    }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const fetchUnmatchedText = async (page = 1, perPage = 20) => {
  const query = new URLSearchParams({ page, per_page: perPage });
  const res = await fetch(`${API_URL}/api/v1/memberships/unmatched?${query}`, {
    credentials: "include",
  });
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

export const fetchJurisdictionHistory = async (jurisdictionOcdid, page = 1, perPage = 25) => {
  const params = new URLSearchParams({ jurisdiction_ocdid: jurisdictionOcdid, page, per_page: perPage });
  const res = await fetch(`/api/v1/jurisdictions/history?${params}`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

// What the jurisdiction is still waiting on, plus the two scalars a page needs about its
// whole history. Replaces fetching every changeset to derive four things from the array.
export const fetchJurisdictionInFlight = async (jurisdictionOcdid) => {
  const params = new URLSearchParams({ jurisdiction_ocdid: jurisdictionOcdid });
  const res = await fetch(`/api/v1/jurisdictions/in-flight?${params}`, {
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

export const fetchReview = async (changesetId) => {
  const res = await fetch(`${API_URL}/api/v1/reviews/${changesetId}/review`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const fetchReportedIssues = async (changesetId) => {
  const res = await fetch(`${API_URL}/api/v1/reviews/${changesetId}/issues`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const reportReviewIssue = async (changesetId, description) => {
  const res = await fetch(`${API_URL}/api/v1/reviews/${changesetId}/issues`, {
    credentials: "include",
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": getCsrfCookie() },
    body: JSON.stringify({ description }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const dismissReview = async (changeset_id) => {
  const res = await fetch(`${API_URL}/api/v1/reviews/${changeset_id}`, {
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

const PATCHABLE_JURISDICTION_FIELDS = ["url", "geoid", "population"];

// Only the keys actually present are sent. Coercing an absent field to null would ask the
// server to clear it: null means "a human set this to nothing", and an untouched field has
// to stay out of the payload entirely to mean "leave it alone".
const jurisdictionPatchBody = (jurisdictionOcdid, data) => {
  const body = { jurisdiction_ocdid: jurisdictionOcdid };
  for (const field of PATCHABLE_JURISDICTION_FIELDS) {
    if (!(field in data)) continue;
    const value = data[field];
    if (field === "population") {
      body.population = value === null || value === "" ? null : Number(value);
    } else {
      body[field] = value;
    }
  }
  return body;
};

export const patchJurisdictionData = async (jurisdictionOcdid, data) => {
  const res = await fetch(`${API_URL}/api/v1/jurisdictions/data`, {
    method: "PATCH",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": getCsrfCookie(),
    },
    body: JSON.stringify(jurisdictionPatchBody(jurisdictionOcdid, data)),
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
export const triggerPipelineRun = async (jurisdictionOcdid, name, url, sourceUrls) => {
  const res = await fetch(`${API_URL}/api/v1/pipeline_runs`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": getCsrfCookie(),
    },
    body: JSON.stringify({
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

// Live Temporal state for a run still in flight. Admin-gated, so a 403 is an ordinary
// outcome for most viewers — resolves to null rather than throwing, and the caller shows
// nothing. Diagnostics must never be the reason a page fails to render.
export const fetchTemporalWorkflowState = async (changesetId) => {
  const res = await fetch(`${API_URL}/api/v1/pipeline_runs/${changesetId}/temporal-workflow-state`, {
    credentials: "include",
  });
  if (!res.ok) return null;
  const body = await res.json().catch(() => ({}));
  return body.data ?? null;
};

export const cancelPipelineRun = async (changesetId) => {
  const res = await fetch(`${API_URL}/api/v1/pipeline_runs/${changesetId}/cancel`, {
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

export const fetchPullRequestByRequestId = async (changesetId) => {
  const res = await fetch(`${API_URL}/api/v1/reviews/by-request/${changesetId}`, {
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

// ── Curated-sheet imports ────────────────────────────────────────────────────

const IMPORTS_URL = `${API_URL}/api/internal/imports`;

async function importsRequest(path, method) {
  const res = await fetch(`${IMPORTS_URL}${path}`, {
    credentials: "include",
    method,
    headers: { "X-CSRF-Token": getCsrfCookie() },
  });
  const body = await res.json();
  // The router's failures are all actionable text (unshared sheet, import already
  // running), so the message is worth more to the caller than the status code.
  if (!res.ok) throw new Error(body.error || `HTTP ${res.status}`);
  return body;
}

export const startImport = async () => importsRequest("", "POST");

export const fetchLatestImport = async () => importsRequest("/latest", "GET");

export const fetchSheetUrl = async () => importsRequest("/sheet", "GET");

export const fetchImportHistory = async () =>
  importsRequest("/history", "GET");

export const fetchImportProgress = async (batchId) =>
  importsRequest(`/${batchId}`, "GET");

export const fetchBatchReview = async (batchId) =>
  importsRequest(`/${batchId}/review`, "GET");

export const publishBatch = async (batchId, jurisdictionOcdids) => {
  const res = await fetch(`${IMPORTS_URL}/${batchId}/publish`, {
    credentials: "include",
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": getCsrfCookie(),
    },
    body: JSON.stringify({ jurisdiction_ocdids: jurisdictionOcdids }),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.error || `HTTP ${res.status}`);
  return body;
};

// ── API keys ─────────────────────────────────────────────────────────────────

const API_KEYS_URL = `${API_URL}/api/internal/api_keys`;

async function apiKeysRequest(path, method) {
  const res = await fetch(`${API_KEYS_URL}${path}`, {
    credentials: "include",
    method,
    headers: { "X-CSRF-Token": getCsrfCookie() },
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `HTTP ${res.status}`);
  return body;
}

export const fetchApiKeys = async () => apiKeysRequest("", "GET");

export const createApiKey = async () => apiKeysRequest("", "POST");

export const revokeApiKey = async (apiKeyId) =>
  apiKeysRequest(`/${apiKeyId}/revoke`, "POST");

export const deleteApiKey = async (apiKeyId) =>
  apiKeysRequest(`/${apiKeyId}`, "DELETE");
