// The candidate list the profile page's history widget links into: everything of a user's
// that can currently be rolled back, one flat list, no jurisdiction picker.

import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import {
  fetchAdminUser,
  fetchRollbackCandidates,
  rollbackUserAssertions,
} from "../../api.js";
import {
  type AdminUser,
  type RollbackCandidate,
  ASSERTION_STATUS_ACTIVE,
  fieldLabel,
  formatValue,
  userLabel,
} from "../user-profile-page/shared.js";
import { SectionNav, userSection } from "../../components/section-nav/index.js";
import { Pagination } from "../../components/pagination/index.js";
import {
  jurisdictionOcdidToFriendly,
  jurisdictionOcdidToPath,
} from "../../components/ocdid-utils.js";
import "../../components/status-toast/status-toast.js";
import "../../components/status-toast/status-toast.css";
import "../user-profile-page/user-profile-page.css";
// Reused, not copied — the real activity feed's row is the visual reference, so this can
// never drift from what `/activity` itself renders.
import "../activity-page/activity-page.css";
import "./confirm-rollback-modal.js";
import "./user-history-page.css";

const TOAST_TIMEOUT_MS = 10_000;
const PER_PAGE = 20;

function formatDate(iso: string) {
  return new Date(iso).toLocaleString();
}

interface UserHistoryPageProps {
  target_user_id: string;
  username: string;
}

function UserHistoryPage({ target_user_id, username }: UserHistoryPageProps) {
  const [user, setUser] = useState<AdminUser | null>(null);

  const [candidates, setCandidates] = useState<RollbackCandidate[]>([]);
  const [candidatesLoading, setCandidatesLoading] = useState(true);
  const [candidatesLoadError, setCandidatesLoadError] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [reason, setReason] = useState("");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    if (!target_user_id) return;
    fetchAdminUser(target_user_id).then((result: { data: AdminUser }) => setUser(result.data));
  }, [target_user_id]);

  const refreshCandidates = () => {
    setCandidatesLoading(true);
    setCandidatesLoadError(null);
    fetchRollbackCandidates(target_user_id)
      .then((result: { data: RollbackCandidate[] }) => {
        setCandidates(result.data);
        setSelected(new Set());
        setPage(1);
      })
      .catch((err: Error) => setCandidatesLoadError(err.message))
      .finally(() => setCandidatesLoading(false));
  };

  useEffect(() => {
    if (!target_user_id) return;
    refreshCandidates();
  }, [target_user_id]);

  const showToast = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(null), TOAST_TIMEOUT_MS);
  };

  const toggleOne = (assertionId: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(assertionId)) next.delete(assertionId);
      else next.add(assertionId);
      return next;
    });
  };

  const totalPages = Math.max(1, Math.ceil(candidates.length / PER_PAGE));
  const pageCandidates = candidates.slice((page - 1) * PER_PAGE, page * PER_PAGE);
  // Only an ACTIVE assertion is a real rollback candidate — superseded/withdrawn rows are
  // history the page shows but never lets you (re-)select.
  const pageActiveIds = pageCandidates
    .filter((c) => c.status === ASSERTION_STATUS_ACTIVE)
    .map((c) => c.assertion_id);

  // "Select all" is scoped to this page's visible rows, not the whole history — a second
  // page's items are selected by turning to that page, same as checking each box by hand.
  const allSelected =
    pageActiveIds.length > 0 && pageActiveIds.every((id) => selected.has(id));
  const toggleAll = () => {
    setSelected((prev) => {
      const next = new Set(prev);
      pageActiveIds.forEach((id) => (allSelected ? next.delete(id) : next.add(id)));
      return next;
    });
  };

  const label = userLabel(user, username);

  const handleRollbackClick = () => {
    if (selected.size === 0) return;
    setConfirmOpen(true);
  };

  const handleConfirmCancel = () => {
    if (submitting) return;
    setConfirmOpen(false);
  };

  const handleConfirmed = async () => {
    setSubmitting(true);
    try {
      const result = await rollbackUserAssertions(target_user_id, Array.from(selected), reason);
      const withdrawn = result.data.withdrawn as number;
      showToast(`Rolled back ${withdrawn} change${withdrawn === 1 ? "" : "s"} for ${label}`);
      setReason("");
      setConfirmOpen(false);
      refreshCandidates();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      showToast(`Rollback failed: ${message}`);
    } finally {
      setSubmitting(false);
    }
  };

  return html`
    <main class="user-profile-page page-content">
      <div class="sectioned">
        ${SectionNav("user", userSection(username), `/~${username}/history`)}
        <div class="secbody">
          <h1 class="user-profile-page__title">History</h1>

          ${candidatesLoading ? html`<p class="user-profile-page__status">Loading…</p>` : null}
          ${candidatesLoadError
            ? html`<p class="user-profile-page__status user-profile-page__error">
                ${candidatesLoadError}
              </p>`
            : null}
          ${!candidatesLoading && !candidatesLoadError && candidates.length === 0
            ? html`<p class="user-profile-page__status">No history yet.</p>`
            : null}
          ${!candidatesLoading && !candidatesLoadError && candidates.length > 0
            ? html`
                <label class="candidate-row-list__select-all">
                  <input
                    type="checkbox"
                    .checked=${allSelected}
                    ?disabled=${pageActiveIds.length === 0}
                    @change=${toggleAll}
                  />
                  Select all (${pageActiveIds.length})
                </label>
                <div class="activity-row-list candidate-row-list">
                  ${pageCandidates.map(
                    (candidate) => html`
                      <label
                        class="activity-row candidate-row ${candidate.status !==
                        ASSERTION_STATUS_ACTIVE
                          ? "activity-row--quarantined"
                          : ""}"
                      >
                        <input
                          type="checkbox"
                          class="candidate-row__checkbox"
                          .checked=${selected.has(candidate.assertion_id)}
                          ?disabled=${candidate.status !== ASSERTION_STATUS_ACTIVE}
                          @change=${() => toggleOne(candidate.assertion_id)}
                        />
                        <div class="activity-row__head">
                          <span class="activity-row__type">${fieldLabel(candidate.field_path)}</span>
                          <span class="activity-row__who">
                            ${candidate.entity_label}
                            <span class="activity-row__role">${candidate.status}</span>
                          </span>
                          <span class="activity-row__what">
                            <a
                              href="/${jurisdictionOcdidToPath(candidate.jurisdiction_ocdid)}"
                              target="_blank"
                              rel="noopener"
                              >${jurisdictionOcdidToFriendly(candidate.jurisdiction_ocdid)}</a
                            >
                            <span class="activity-row__summary"
                              >${formatValue(candidate.value)}</span
                            >
                          </span>
                          <span></span>
                          <span class="activity-row__at">${formatDate(candidate.created_at)}</span>
                        </div>
                      </label>
                    `,
                  )}
                </div>
                ${Pagination({
                  page,
                  totalPages,
                  onPrevious: () => setPage(page - 1),
                  onNext: () => setPage(page + 1),
                })}
                <label class="candidate-list__reason-label" for="user-history-reason">
                  Reason (optional)
                </label>
                <input
                  id="user-history-reason"
                  class="candidate-list__reason-input"
                  type="text"
                  placeholder="Why is this being rolled back?"
                  .value=${reason}
                  @input=${(e: Event) => setReason((e.target as HTMLInputElement).value)}
                />
                <button
                  class="btn btn-sm destructive user-profile-page__rollback-button"
                  @click=${handleRollbackClick}
                  ?disabled=${selected.size === 0}
                >
                  Roll back ${selected.size} selected
                </button>
              `
            : null}

          ${toast
            ? html`<status-toast .message=${toast} .onDismiss=${() => setToast(null)}></status-toast>`
            : null}
          ${confirmOpen
            ? html`
                <confirm-rollback-modal
                  .count=${selected.size}
                  .userLabel=${label}
                  .submitting=${submitting}
                  @modal-close=${handleConfirmCancel}
                  @rollback-confirmed-final=${handleConfirmed}
                ></confirm-rollback-modal>
              `
            : null}
        </div>
      </div>
    </main>
  `;
}

customElements.define(
  "user-history-page",
  component(UserHistoryPage as any, {
    useShadowDOM: false,
    observedAttributes: ["target_user_id", "username"],
  }),
);
export default UserHistoryPage;
