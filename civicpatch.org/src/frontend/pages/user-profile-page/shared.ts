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

// Mirrors `ChangesetKind.ROLLBACK` (shared/utils/statuses.py). A rollback is listed --- undoing
// an undo is rolling back the rollback --- but never swept by "select all", or select-all would
// alternate between doing and undoing.
export const CHANGESET_KIND_ROLLBACK = "rollback";

// One changeset, the rollback unit since 2026-09-24. It replaced a per-claim candidate: one
// action is undone or it is not, and a changeset is the only thing spanning the facts one action
// filed. `comment` is set on a rollback and null on everything else.
export type RollbackCandidate = {
  changeset_id: string;
  kind: string;
  jurisdiction_ocdid: string;
  jurisdiction_name: string;
  comment: string | null;
  published_at: string;
};

const KIND_LABELS: Record<string, string> = {
  scrape: "Scrape",
  sheet_import: "Sheet import",
  people_edit: "Roster edit",
  jurisdiction_edit: "Jurisdiction edit",
  rollback: "Rollback",
};

export function changesetKindLabel(kind: string): string {
  return KIND_LABELS[kind] ?? kind.replace(/_/g, " ");
}

export function userLabel(user: AdminUser | null, fallback: string): string {
  return user ? (user.email ?? user.username ?? fallback) : fallback;
}
