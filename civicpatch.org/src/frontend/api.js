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

export const fetchIssueCounts = async (stateCode, kind) => {
  const params = new URLSearchParams();
  if (stateCode) params.set("state_code", stateCode);
  if (kind) params.set("kind", kind);
  const query = params.toString() ? `?${params}` : "";
  const res = await fetch(`${API_URL}/api/v1/pipeline_runs/issues/counts${query}`, { credentials: "include" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const fetchChangeLogs = async (authors, page = 1, perPage = 20) => {
  const params = new URLSearchParams({ authors, page, per_page: perPage });
  const res = await fetch(`${API_URL}/api/v1/change_logs?${params}`, { credentials: "include" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const fetchJobIssues = async (tags, page, perPage, sort, stateCode, showArchived = false, kind) => {
  const params = new URLSearchParams({ page, per_page: perPage, sort });
  if (tags && tags.length) params.set("tags", tags.join(","));
  if (stateCode) params.set("state_code", stateCode);
  if (showArchived) params.set("show_archived", "true");
  if (kind) params.set("kind", kind);
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

export const dismissIssues = async (issueIds) => {
  const res = await fetch(`${API_URL}/api/v1/pipeline_runs/issues/dismiss`, {
    credentials: "include",
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": getCsrfCookie() },
    body: JSON.stringify({ issue_ids: issueIds }),
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

export const fetchPeopleAssertions = async (jurisdictionOcdid) => {
  const params = new URLSearchParams({ jurisdiction_ocdid: jurisdictionOcdid });
  const res = await fetch(`${API_URL}/api/v1/people/assertions?${params}`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
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

export const fetchBlogPosts = async (limit = 3) => {
  const params = new URLSearchParams({ limit });
  const res = await fetch(`${API_URL}/api/v1/blog/posts?${params}`, {
    credentials: "include",
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

export const fetchRecentPublications = async (limit = 10) => {
  const params = new URLSearchParams({ limit });
  const res = await fetch(`${API_URL}/api/v1/change_logs/recent-publications?${params}`, {
    credentials: "include",
  });
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

export const fetchLeaderboard = async (period) => {
  const params = new URLSearchParams();
  if (period) params.set("period", period);
  const query = params.toString() ? `?${params}` : "";
  const res = await fetch(`${API_URL}/api/v1/leaderboard${query}`, { credentials: "include" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

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

export const fetchTemporalWorkflowState = async (changesetId) => {
  const res = await fetch(`${API_URL}/api/v1/pipeline_runs/${changesetId}/temporal-workflow-state`, {
    credentials: "include",
  });
  if (!res.ok) return null;
  const body = await res.json().catch(() => ({}));
  return body.data ?? null;
};

export const cancelPipelineRun = async (pipelineRunId) => {
  const res = await fetch(`${API_URL}/api/v1/pipeline_runs/${pipelineRunId}/cancel`, {
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

export const fetchAvailableReviewStates = async () => {
  const res = await fetch(`${API_URL}/api/v1/review-sessions/available-states`, { credentials: "include" });
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

export const createReviewSession = async (stateCode, sessionLength) => {
  const res = await fetch(`${API_URL}/api/v1/review-sessions`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": getCsrfCookie() },
    body: JSON.stringify({ state_code: stateCode, session_length: sessionLength }),
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

export const fetchAdminUser = async (userId) => {
  const res = await fetch(`${API_URL}/api/admin/users/${userId}`, {
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

export const fetchRollbackCandidates = async (userId) => {
  const res = await fetch(`${API_URL}/api/admin/users/${userId}/rollback-candidates`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const rollbackUserAssertions = async (userId, assertionIds, reason) => {
  const res = await fetch(`${API_URL}/api/admin/users/${userId}/rollback`, {
    credentials: "include",
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": getCsrfCookie(),
    },
    body: JSON.stringify({ assertion_ids: assertionIds, reason: reason || null }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(parseSaveError(body, res.status));
  }
  return res.json();
};

export const setUsername = async (username) => {
  const res = await fetch(`${API_URL}/api/v1/user/username`, {
    credentials: "include",
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": getCsrfCookie(),
    },
    body: JSON.stringify({ username }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const err = new Error(parseSaveError(body, res.status));
    err.status = res.status;
    throw err;
  }
  return res.json();
};

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

export const fetchJurisdiction = async (jurisdictionOcdid) => {
  const params = new URLSearchParams({ jurisdiction_ocdid: jurisdictionOcdid });
  const res = await fetch(`${API_URL}/api/v1/jurisdictions?${params}`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

const IMPORTS_URL = `${API_URL}/api/v1/imports`;

async function importsRequest(path, method) {
  const res = await fetch(`${IMPORTS_URL}${path}`, {
    credentials: "include",
    method,
    headers: { "X-CSRF-Token": getCsrfCookie() },
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.error || `HTTP ${res.status}`);
  return body;
}

export const startImport = async () => importsRequest("", "POST");

export const fetchLatestImport = async () => importsRequest("/latest", "GET");

export const fetchSheetUrl = async () => importsRequest("/sheet", "GET");

export const fetchImportHistory = async (page = 1, perPage = 10) =>
  importsRequest(`/history?page=${page}&per_page=${perPage}`, "GET");

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

const API_KEYS_URL = `${API_URL}/api/v1/api_keys`;

async function apiKeysRequest(path, method) {
  const res = await fetch(`${API_KEYS_URL}${path}`, {
    credentials: "include",
    method,
    headers: { "X-CSRF-Token": getCsrfCookie() },
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(parseSaveError(body, res.status));
  return body;
}

export const fetchApiKeys = async () => apiKeysRequest("", "GET");

export const createApiKey = async () => apiKeysRequest("", "POST");

export const revokeApiKey = async (apiKeyId) =>
  apiKeysRequest(`/${apiKeyId}/revoke`, "POST");

export const deleteApiKey = async (apiKeyId) =>
  apiKeysRequest(`/${apiKeyId}`, "DELETE");

const SUMMARIES_URL = `${API_URL}/api/v1/changeset_summaries`;

const summariesRequest = async (path) => {
  const res = await fetch(`${SUMMARIES_URL}${path}`, { credentials: "include" });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(parseSaveError(body, res.status));
  return body.data;
};

export const fetchStateRollup = async (windowDays) =>
  summariesRequest(`/rollup?window_days=${windowDays}`);

export const fetchStateCalendar = async (windowDays) =>
  summariesRequest(`/calendar?window_days=${windowDays}`);

export const fetchStateSpend = async (windowDays) => {
  const res = await fetch(
    `${API_URL}/api/v1/pipeline_runs/spend?window_days=${windowDays}`,
    { credentials: "include" },
  );
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(parseSaveError(body, res.status));
  return body.data;
};

const SCRAPE_SETTINGS_URL = `${API_URL}/api/v1/scrape_settings`;

const scrapeSettingsRequest = async (path, options = {}) => {
  const res = await fetch(`${SCRAPE_SETTINGS_URL}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": getCsrfCookie() },
    ...options,
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(parseSaveError(body, res.status));
  return body.data;
};

export const fetchStateScrapeSettings = async (state) =>
  scrapeSettingsRequest(`/${encodeURIComponent(state)}`);

export const fetchGlobalScrapeSettings = async () => scrapeSettingsRequest("/global");

export const saveGlobalCap = async (monthlyCapUsd) =>
  scrapeSettingsRequest("/global", {
    method: "PUT",
    body: JSON.stringify({ monthly_cap_usd: monthlyCapUsd }),
  });

export const saveCadence = async (state, cadenceDays, cadenceAnchor) =>
  scrapeSettingsRequest(`/${encodeURIComponent(state)}/cadence`, {
    method: "PUT",
    body: JSON.stringify({ cadence_days: cadenceDays, cadence_anchor: cadenceAnchor }),
  });

export const saveCaps = async (state, pipelineRunCapUsd, monthlyCapUsd) =>
  scrapeSettingsRequest(`/${encodeURIComponent(state)}/caps`, {
    method: "PUT",
    body: JSON.stringify({
      pipeline_run_cap_usd: pipelineRunCapUsd,
      monthly_cap_usd: monthlyCapUsd,
    }),
  });

export const fetchJurisdictionStates = async () => {
  const res = await fetch(`${API_URL}/api/v1/jurisdictions/states`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()).data;
};

export const startStateScrape = async (state, numJurisdictions = null) => {
  const res = await fetch(`${API_URL}/api/v1/pipeline_runs/batch`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": getCsrfCookie() },
    body: JSON.stringify({ state, num_jurisdictions: numJurisdictions }),
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(parseSaveError(body, res.status));
  return body;
};
