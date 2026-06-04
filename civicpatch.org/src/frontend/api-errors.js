// A FastAPI validation error comes back as {detail: [{loc, msg}]}; our own
// handlers use {error}. Pull a person + field message out of the validation case
// so the caller can show "Jane Smith — phones: Invalid phone number" and jump to
// the right row, instead of a bare "HTTP 422". loc is ["body","data",<index>,<field>,...].
export const parseSaveError = (body, status, people) => {
  const detail = Array.isArray(body.detail) ? body.detail[0] : null;
  if (!detail) return body.error || `HTTP ${status}`;
  const loc = Array.isArray(detail.loc) ? detail.loc : [];
  const field = [...loc].reverse().find((part) => typeof part === "string" && part !== "body" && part !== "data");
  const msg = (detail.msg || "Invalid value").replace(/^Value error,\s*/, "");
  const label = field ? `${field}: ${msg}` : msg;

  const dataPos = loc.indexOf("data");
  const index = dataPos >= 0 && typeof loc[dataPos + 1] === "number" ? loc[dataPos + 1] : null;
  const name = index !== null && people && people[index] ? people[index].name : null;
  return name ? `${name} — ${label}` : label;
};
