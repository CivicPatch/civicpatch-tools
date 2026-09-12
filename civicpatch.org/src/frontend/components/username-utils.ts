const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-([0-9a-f]{12})$/i;

// A username is a raw uuid only for a legacy account backfilled from its own id (192, 193) —
// display just the trailing segment rather than the whole thing.
export function shortenIfUuid(username: string): string {
  const match = username.match(UUID_PATTERN);
  return match ? match[1] : username;
}

export const MAX_USERNAME_LENGTH = 50;
const USERNAME_PATTERN = /^[A-Za-z0-9._-]+$/;

// Mirrors _validate_username (schemas/common.py) — same length cap and charset, so a bad
// value is caught while typing rather than at the 409/422 round trip. Shared by the sign-up
// username page and the settings username form, the only two places that set it.
export function usernameError(value: string): string | null {
  const text = value.trim();
  if (!text) return "Username is required";
  if (text.length > MAX_USERNAME_LENGTH) {
    return `Username too long (max ${MAX_USERNAME_LENGTH})`;
  }
  if (!USERNAME_PATTERN.test(text)) {
    return "Username may only contain letters, numbers, '.', '_', and '-'";
  }
  return null;
}
