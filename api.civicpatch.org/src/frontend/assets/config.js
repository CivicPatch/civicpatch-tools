export const config = {
  apiUrl: window.__ENV__?.API_URL ?? "http://localhost:8000",
  environment: window.__ENV__?.ENVIRONMENT ?? "development",
};