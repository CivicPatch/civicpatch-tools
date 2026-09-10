// Shared between user-profile-page and user-history-page: the user shape both fetch, and the
// candidate-row formatting the history page renders.

export type AdminUser = {
  id: string;
  email: string | null;
  display_name: string | null;
  provider: string;
  role: string;
  last_login_at: string | null;
};

export type RollbackCandidate = {
  assertion_id: string;
  entity_id: string;
  entity_label: string;
  field_path: string;
  value: unknown;
  jurisdiction_ocdid: string;
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
  return user ? (user.email ?? user.display_name ?? fallback) : fallback;
}
