import { config } from "./assets/config.js";

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

export const updatePullRequestData = async (
  request_id,
  jurisdiction_ocdid,
  data,
) => {
  const response = await fetch(`${API_URL}/api/v1/pull_requests/data`, {
    credentials: "include",
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": getCsrfCookie(),
    },
    body: JSON.stringify({ request_id, jurisdiction_ocdid, data }),
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
};

export const fetchPullRequests = async (jurisdictionOcdid) => {
  const params = new URLSearchParams({ jurisdiction_ocdid: jurisdictionOcdid });
  const res = await fetch(`${API_URL}/api/v1/pull_requests/with-data?${params}`, {
    credentials: "include",
  });
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

export const saveAndMerge = async (pullRequestNumber, request_id, jurisdiction_ocdid, people) => {
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
    const err = new Error(body.error || `HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }

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

export const fetchJurisdictionConfig = async (ocdid) => {
  const params = new URLSearchParams({ ocdid });
  const res = await fetch(`/api/v1/jurisdictions/config?${params}`, { credentials: "include" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const putJurisdictionConfig = async (body) => {
  const res = await fetch(`/api/v1/jurisdictions/config`, {
    method: "PUT",
    credentials: "include",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": getCsrfCookie() },
    body: JSON.stringify(body),
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

export const deletePerson = async (personId) => {
  const res = await fetch(`${API_URL}/api/v1/people/${personId}`, {
    method: "DELETE",
    credentials: "include",
    headers: { "X-CSRF-Token": getCsrfCookie() },
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
    throw new Error(body.error || `HTTP ${res.status}`);
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
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
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


export const pauseReviewSession = async (sessionId) => {
  const res = await fetch(`${API_URL}/api/v1/review-sessions/${sessionId}/pause`, {
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

export const fetchNotes = async (jurisdictionOcdid, page = 1, perPage = 10) => {
  const params = new URLSearchParams({ jurisdiction_ocdid: jurisdictionOcdid, page, per_page: perPage });
  const res = await fetch(`${API_URL}/api/v1/notes?${params}`, { credentials: "include" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const createNote = async (jurisdictionOcdid, body) => {
  const res = await fetch(`${API_URL}/api/v1/notes`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": getCsrfCookie() },
    body: JSON.stringify({ jurisdiction_ocdid: jurisdictionOcdid, body }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};


