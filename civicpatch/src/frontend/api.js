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

export const fetchPullRequestsWithData = (page, perPage) =>
  fetch(
    `${API_URL}/api/v1/pull_requests/with-data?page=${page}&per_page=${perPage}`,
    {
      credentials: "include",
    },
  ).then((res) => {
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  });

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
