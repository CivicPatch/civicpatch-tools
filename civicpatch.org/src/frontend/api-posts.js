import { getCsrfCookie } from "./api-csrf.js";

export const deletePost = async (postId, intoPostId) => {
  const query = intoPostId ? `?${new URLSearchParams({ into: intoPostId })}` : "";
  const res = await fetch(`/api/v1/posts/${postId}${query}`, {
    method: "DELETE",
    credentials: "include",
    headers: { "X-CSRF-Token": getCsrfCookie() },
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.error || `HTTP ${res.status}`);
  return body;
};
