import { getCsrfCookie } from "./api-csrf.js";

export const fetchOrganizations = async (jurisdictionOcdid) => {
  const res = await fetch(`/api/v1/organizations/${jurisdictionOcdid}`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const createOrganization = async (jurisdictionOcdid, body) => {
  const res = await fetch(`/api/v1/organizations/${jurisdictionOcdid}`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": getCsrfCookie(),
    },
    body: JSON.stringify(body),
  });
  if (res.status === 409)
    throw new Error("An organization with that name already exists.");
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const updateOrganization = async (organizationId, { name, url }) => {
  const res = await fetch(`/api/v1/organizations/${organizationId}`, {
    method: "PATCH",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": getCsrfCookie(),
    },
    body: JSON.stringify({ name, url }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const setDefaultOrganization = async (organizationId) => {
  const res = await fetch(`/api/v1/organizations/${organizationId}/default`, {
    method: "POST",
    credentials: "include",
    headers: { "X-CSRF-Token": getCsrfCookie() },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const deleteOrganization = async (organizationId) => {
  const res = await fetch(`/api/v1/organizations/${organizationId}`, {
    method: "DELETE",
    credentials: "include",
    headers: { "X-CSRF-Token": getCsrfCookie() },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};
