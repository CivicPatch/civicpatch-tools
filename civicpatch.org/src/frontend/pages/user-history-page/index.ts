// The candidate list `user-profile-page`'s "History → More" links into: everything of a
// user's that can currently be rolled back, one flat list, no jurisdiction picker.

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
  fieldLabel,
  formatValue,
  userLabel,
} from "../user-profile-page/shared.js";
import { SectionNav, userSection } from "../../components/section-nav/index.js";
import "../admin-page/status-toast.js";
import "../user-profile-page/user-profile-page.css";
import "./confirm-rollback-modal.js";
import "./user-history-page.css";

const TOAST_TIMEOUT_MS = 10_000;

interface UserHistoryPageProps {
  target_user_id: string;
}

function UserHistoryPage({ target_user_id }: UserHistoryPageProps) {
  const [user, setUser] = useState<AdminUser | null>(null);

  const [candidates, setCandidates] = useState<RollbackCandidate[]>([]);
  const [candidatesLoading, setCandidatesLoading] = useState(true);
  const [candidatesLoadError, setCandidatesLoadError] = useState<string | null>(null);

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
        setSelected(new Set(result.data.map((c) => c.assertion_id)));
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

  const allSelected = candidates.length > 0 && selected.size === candidates.length;
  const toggleAll = () => {
    setSelected(allSelected ? new Set() : new Set(candidates.map((c) => c.assertion_id)));
  };

  const label = userLabel(user, target_user_id);

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
    <div class="sectioned">
      ${SectionNav("user", userSection(target_user_id), `/users/${target_user_id}/history`)}
      <main class="secbody user-profile-page page-content">
      <h1 class="user-profile-page__title">History</h1>

      ${candidatesLoading ? html`<p class="user-profile-page__status">Loading…</p>` : null}
      ${candidatesLoadError
        ? html`<p class="user-profile-page__status user-profile-page__error">
            ${candidatesLoadError}
          </p>`
        : null}
      ${!candidatesLoading && !candidatesLoadError && candidates.length === 0
        ? html`<p class="user-profile-page__status">No active edits to roll back.</p>`
        : null}
      ${!candidatesLoading && !candidatesLoadError && candidates.length > 0
        ? html`
            <label class="candidate-list__select-all">
              <input type="checkbox" .checked=${allSelected} @change=${toggleAll} />
              Select all (${candidates.length})
            </label>
            <ul class="candidate-list">
              ${candidates.map(
                (candidate) => html`
                  <li class="candidate-list__item">
                    <label>
                      <input
                        type="checkbox"
                        .checked=${selected.has(candidate.assertion_id)}
                        @change=${() => toggleOne(candidate.assertion_id)}
                      />
                      <span class="candidate-list__entity">${candidate.entity_label}</span>
                      <span class="candidate-list__field"
                        >${fieldLabel(candidate.field_path)}</span
                      >
                      <span class="candidate-list__value">${formatValue(candidate.value)}</span>
                    </label>
                    <span class="candidate-list__jurisdiction"
                      >${candidate.jurisdiction_ocdid}</span
                    >
                  </li>
                `,
              )}
            </ul>
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
      </main>
    </div>
  `;
}

customElements.define(
  "user-history-page",
  component(UserHistoryPage as any, {
    useShadowDOM: false,
    observedAttributes: ["target_user_id"],
  }),
);
export default UserHistoryPage;
