// Turn a save/merge error into a human message. Our per-person validation errors come
// back as {detail: [{id, name, field, message}]} — self-describing, so we show
// "Jane Smith — phones: Invalid phone number" with no row lookup. FastAPI's own validation
// errors are {detail: [{loc, msg}]} (e.g. a malformed request_id); our other handlers use {error}.
export const parseSaveError = (body, status) => {
  const detail = Array.isArray(body.detail) ? body.detail[0] : null;
  if (!detail) return body.error || `HTTP ${status}`;

  if (detail.field && detail.message) {
    const msg = detail.message.replace(/^Value error,\s*/, "");
    const label = `${detail.field}: ${msg}`;
    return detail.name ? `${detail.name} — ${label}` : label;
  }

  const loc = Array.isArray(detail.loc) ? detail.loc : [];
  const field = [...loc].reverse().find((part) => typeof part === "string" && part !== "body" && part !== "data");
  const msg = (detail.msg || "Invalid value").replace(/^Value error,\s*/, "");
  return field ? `${field}: ${msg}` : msg;
};
