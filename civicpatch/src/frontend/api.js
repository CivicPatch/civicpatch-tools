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

export const fetchPullRequestsWithData = (page, perPage, stateCode) => {
  const params = new URLSearchParams({ page, per_page: perPage });
  if (stateCode) params.set("state_code", stateCode);
  return fetch(`${API_URL}/api/v1/pull_requests/with-data?${params}`, {
    credentials: "include",
  }).then((res) => {
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  });
};

export const mergePullRequest = (pullRequestNumber) =>
  fetch(`${API_URL}/api/v1/pull_requests/${pullRequestNumber}/merge`, {
    credentials: "include",
    method: "POST",
    headers: {
      "X-CSRF-Token": getCsrfCookie(),
    },
  }).then((res) => {
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  });

export const closePullRequest = (pullRequestNumber) =>
  fetch(`${API_URL}/api/v1/pull_requests/${pullRequestNumber}`, {
    credentials: "include",
    method: "DELETE",
    headers: {
      "X-CSRF-Token": getCsrfCookie(),
    },
  }).then((res) => {
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  });
