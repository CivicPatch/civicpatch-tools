// The candidate list the profile page's history widget links into: the user's published
// changesets from the last week, one flat list, no jurisdiction picker.
//
// One row is one changeset, the rollback unit since 2026-09-24. It used to be one claim per row,
// which meant a single roster edit appeared as several independently-undoable rows even though
// nothing could undo half of it.

import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { ref } from "lit/directives/ref.js";
import { usePagerRef } from "../../hooks/use-pager-ref.js";
import {
  fetchAdminUser,
  fetchRollbackCandidates,
  rollbackUserChangesets,
} from "../../api.js";
import {
  type AdminUser,
  type RollbackCandidate,
  CHANGESET_KIND_ROLLBACK,
  changesetKindLabel,
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
import { formatDateTime } from "../../utils/date-utils.js";

const TOAST_TIMEOUT_MS = 10_000;
const PER_PAGE = 20;

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
  const [comment, setComment] = useState("");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const { listRef, scrollToTop } = usePagerRef<HTMLElement>();

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

  const toggleOne = (changesetId: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(changesetId)) next.delete(changesetId);
      else next.add(changesetId);
      return next;
    });
  };

  const totalPages = Math.max(1, Math.ceil(candidates.length / PER_PAGE));
  const pageCandidates = candidates.slice((page - 1) * PER_PAGE, page * PER_PAGE);
  // A rollback is pickable on its own — undoing an undo is rolling it back — but never swept
  // by "select all", which would otherwise alternate between doing and undoing.
  const pageSweepableIds = pageCandidates
    .filter((c) => c.kind !== CHANGESET_KIND_ROLLBACK)
    .map((c) => c.changeset_id);

  // "Select all" is scoped to this page's visible rows, not the whole history — a second
  // page's items are selected by turning to that page, same as checking each box by hand.
  const allSelected =
    pageSweepableIds.length > 0 && pageSweepableIds.every((id) => selected.has(id));
  const toggleAll = () => {
    setSelected((prev) => {
      const next = new Set(prev);
      pageSweepableIds.forEach((id) => (allSelected ? next.delete(id) : next.add(id)));
      return next;
    });
  };

  const label = userLabel(user, username);

  // Built once so Next/Previous re-orients to the top of the list either way — clicking
  // the bottom pager most often leaves the reader below what just changed above them.
  const pager = Pagination({
    page,
    totalPages,
    onPrevious: () => {
      setPage(page - 1);
      scrollToTop();
    },
    onNext: () => {
      setPage(page + 1);
      scrollToTop();
    },
  });

  // The comment is required: a rollback holds only withdraws, so nothing else records why.
  const handleRollbackClick = () => {
    if (selected.size === 0 || comment.trim() === "") return;
    setConfirmOpen(true);
  };

  const handleConfirmCancel = () => {
    if (submitting) return;
    setConfirmOpen(false);
  };

  const handleConfirmed = async () => {
    setSubmitting(true);
    try {
      const result = await rollbackUserChangesets(
        target_user_id,
        Array.from(selected),
        comment,
      );
      const withdrawn = result.data.withdrawn as number;
      showToast(`Rolled back ${withdrawn} fact${withdrawn === 1 ? "" : "s"} for ${label}`);
      setComment("");
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
                    ?disabled=${pageSweepableIds.length === 0}
                    @change=${toggleAll}
                  />
                  Select all (${pageSweepableIds.length})
                </label>
                ${pager}
                <div class="activity-row-list candidate-row-list" ${ref(listRef)}>
                  ${pageCandidates.map(
                    (candidate) => html`
                      <label
                        class="activity-row candidate-row ${candidate.kind ===
                        CHANGESET_KIND_ROLLBACK
                          ? "candidate-row--rollback"
                          : ""}"
                      >
                        <input
                          type="checkbox"
                          class="candidate-row__checkbox"
                          .checked=${selected.has(candidate.changeset_id)}
                          @change=${() => toggleOne(candidate.changeset_id)}
                        />
                        <div class="activity-row__head">
                          <span class="activity-row__type"
                            >${changesetKindLabel(candidate.kind)}</span
                          >
                          <span class="activity-row__who">
                            <a
                              href="/${jurisdictionOcdidToPath(candidate.jurisdiction_ocdid)}"
                              target="_blank"
                              rel="noopener"
                              >${jurisdictionOcdidToFriendly(candidate.jurisdiction_ocdid)}</a
                            >
                          </span>
                          <span class="activity-row__what">
                            <span class="activity-row__summary">${candidate.comment ?? ""}</span>
                          </span>
                          <span></span>
                          <span class="activity-row__at"
                            >${formatDateTime(candidate.published_at)}</span
                          >
                        </div>
                      </label>
                    `,
                  )}
                </div>
                ${pager}
                <label class="candidate-list__reason-label" for="user-history-comment">
                  Reason
                </label>
                <input
                  id="user-history-comment"
                  class="candidate-list__reason-input"
                  type="text"
                  required
                  placeholder="Why is this being rolled back?"
                  .value=${comment}
                  @input=${(e: Event) => setComment((e.target as HTMLInputElement).value)}
                />
                <button
                  class="btn btn-sm destructive user-profile-page__rollback-button"
                  @click=${handleRollbackClick}
                  ?disabled=${selected.size === 0 || comment.trim() === ""}
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
