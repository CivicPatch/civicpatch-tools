import { config } from './assets/config.js';

const API_URL = config.apiUrl;

export const fetchPullRequestsWithData = (page, perPage) =>
  fetch(`${API_URL}/api/v1/pull_requests/with-data?page=${page}&per_page=${perPage}`, {
    credentials: 'include',
  }).then(res => {
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  });

