// Shared between user-profile-page and user-history-page: the user shape both fetch, and the
// candidate-row formatting the history page renders.

export type AdminUser = {
  id: string;
  email: string | null;
  username: string | null;
  provider: string;
  role: string;
  last_login_at: string | null;
};

// Mirrors `AssertionState` (core/assertion_lifecycle.py) — only "active" is a real rollback
// candidate; "superseded"/"withdrawn" are history the row shows but can't be selected.
export const ASSERTION_STATUS_ACTIVE = "active";

// Mirrors the `kind` check constraint on `assertions` (database/assertions.py) — a "reject"
// row pairs with an "accept" row on the same field rather than competing with it.
export const ASSERTION_KIND_REJECT = "reject";

export type RollbackCandidate = {
  assertion_id: string;
  entity_id: string;
  entity_label: string;
  field_path: string;
  kind: string;
  value: unknown;
  jurisdiction_ocdid: string;
  status: string;
  created_at: string;
};

const FIELD_LABELS: Record<string, string> = {
  name: "Name",
  other_names: "Other names",
  phones: "Phone",
  emails: "Email",
  urls: "Website",
  source_urls: "Source",
  image: "Photo",
  start_date: "Start date",
  end_date: "End date",
  post_id: "Seat",
};

export function fieldLabel(fieldPath: string): string {
  return FIELD_LABELS[fieldPath] ?? fieldPath.replace(/_/g, " ");
}

export function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

export function userLabel(user: AdminUser | null, fallback: string): string {
  return user ? (user.email ?? user.username ?? fallback) : fallback;
}
