const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-([0-9a-f]{12})$/i;

// A username is a raw uuid only for a legacy account backfilled from its own id (192, 193) —
// display just the trailing segment rather than the whole thing.
export function shortenIfUuid(username: string): string {
  const match = username.match(UUID_PATTERN);
  return match ? match[1] : username;
}
