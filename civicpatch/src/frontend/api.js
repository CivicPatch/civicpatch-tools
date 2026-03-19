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
  const res = await fetch(`${API_URL}/api/v1/pull_requests?${params}`, {
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

export const fetchPullRequestsWithData = async (page, perPage, stateCode) => {
  const params = new URLSearchParams({ page, per_page: perPage });
  if (stateCode) params.set("state_code", stateCode);
  const res = await fetch(`${API_URL}/api/v1/pull_requests/with-data?${params}`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const mergePullRequest = async (pullRequestNumber) => {
  const res = await fetch(`${API_URL}/api/v1/pull_requests/${pullRequestNumber}/merge`, {
    credentials: "include",
    method: "POST",
    headers: {
      "X-CSRF-Token": getCsrfCookie(),
    },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
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

export const closePullRequest = async (pullRequestNumber) => {
  const res = await fetch(`${API_URL}/api/v1/pull_requests/${pullRequestNumber}`, {
    credentials: "include",
    method: "DELETE",
    headers: {
      "X-CSRF-Token": getCsrfCookie(),
    },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};
