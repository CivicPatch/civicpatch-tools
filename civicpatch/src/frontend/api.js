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

export const fetchJobsWithErrors = async (stateCode) => {
  const params = new URLSearchParams();
  if (stateCode) params.set("state_code", stateCode);
  const res = await fetch(`${API_URL}/api/v1/jobs/errors?${params}`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const fetchUnrecognizedRoles = async (stateCode) => {
  const params = new URLSearchParams();
  if (stateCode) params.set("state_code", stateCode);
  const res = await fetch(`${API_URL}/api/v1/jobs/unrecognized-roles?${params}`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const fetchPullRequestsWithData = async (page, perPage, stateCode) => {
  const params = new URLSearchParams({ page, per_page: perPage });
  if (stateCode) params.set("state_code", stateCode);
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
  return res.json();
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

export const fetchJurisdictionHistory = async (jurisdictionOcdid) => {
  const params = new URLSearchParams({ jurisdiction_ocdid: jurisdictionOcdid });
  const res = await fetch(`/api/api_proxy/jurisdictions/history?${params}`, {
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

export const resolveJob = async (requestId) => {
  const res = await fetch(`${API_URL}/api/v1/jobs/${requestId}/status`, {
    credentials: "include",
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": getCsrfCookie(),
    },
    body: JSON.stringify({ status: "RESOLVED" }),
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

export const fetchPeople = async (jurisdictionOcdid) => {
  const params = new URLSearchParams({ jurisdiction_ocdid: jurisdictionOcdid });
  const res = await fetch(`/api/api_proxy/people?${params}`, { credentials: "include" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const fetchDashboard = async () => {
  const res = await fetch(`${API_URL}/api/v1/data/dashboard`, { credentials: "include" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

/** Jobs */
export const triggerRemoteJob = async (jurisdictionOcdid, name, url) => {
  const res = await fetch(`${API_URL}/api/v1/jobs`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": getCsrfCookie(),
    },
    body: JSON.stringify({ jurisdiction_ocdid: jurisdictionOcdid, name, url }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const fetchDuplicatePrJurisdictionJobs = async () => {
  const res = await fetch(`${API_URL}/api/v1/jobs/duplicates`, { credentials: "include" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const closeStaleDuplicatePrs = async () => {
  const res = await fetch(`${API_URL}/api/v1/jobs/duplicates/close-stale`, {
    method: "POST",
    credentials: "include",
    headers: { "X-CSRF-Token": getCsrfCookie() },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const fetchJurisdictionsGeojson = async (lat, lng, zoom) => {
  const params = new URLSearchParams({ lat, long: lng, zoom });
  const res = await fetch(`/api/api_proxy/jurisdictions/geojson?${params}`, { credentials: "include" });
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

export const passReviewSession = async (sessionId, entryNumber) => {
  const res = await fetch(`${API_URL}/api/v1/review-sessions/${sessionId}/pass`, {
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

