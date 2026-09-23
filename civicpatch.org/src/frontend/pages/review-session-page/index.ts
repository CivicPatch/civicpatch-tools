import { html } from "lit-html";
import { component } from "haunted";
import { useLocalStorage, PERSIST_FOREVER } from "../../hooks/use-local-storage.js";
import { STORAGE_KEYS } from "../../utils/storage-keys.js";
import { useAuth } from "../../hooks/useAuth.js";
import { editJurisdictionRoster } from "../../api.js";
import type { OfficeEdit } from "../../components/person-editor/office-edits.js";
import { useReviewActions } from "../../hooks/use-review-actions.js";
import { REVIEW_ACTION } from "../../components/review-card/review-action.js";
import { useReviewSession } from "./use-review-session.js";
import { landingUrl, STATE_PARAM } from "../review-routes.js";
import { StateKind } from "./review-state.js";
import "./review-session.js";
import "../../components/review-log/index.js";
import "./review-session-page.css";

function getStateFromUrl() {
  return (new URLSearchParams(window.location.search).get(STATE_PARAM) || "").toLowerCase();
}

function ReviewSessionPage() {
  const [defaultState] = useLocalStorage(STORAGE_KEYS.DEFAULT_STATE, "", { ttl: PERSIST_FOREVER });
  const stateCode = (getStateFromUrl() || defaultState || "").toLowerCase();

  const { user, permissions } = useAuth();
  const { actionState, entries: reviewLogEntries, trackApprove, trackReject } = useReviewActions();
  const { fsm, advance, back, navigateTo, merge, save, rejectScrape, endSession } = useReviewSession(stateCode, {
    trackApprove,
    trackReject,
  });

  const reviewing = fsm.kind === StateKind.REVIEWING ? fsm : null;
  const currentEntry = reviewing?.current_entry ?? null;
  const session = reviewing?.session ?? null;

  const changesetId = currentEntry?.changeset_id;
  const isRejecting = changesetId != null && actionState[changesetId]?.status === REVIEW_ACTION.REJECTING;
  // Any signed-in user — assigning an existing post is looser than reviewer-only actions
  // like rejecting a scrape (see routers/api/memberships.py).
  const canAssignMembership = !!user?.authenticated;

  // One call for the whole card: the fields a reviewer corrected and the posts they picked are
  // one answer about one person, so they are one payload under one changeset. A failure stops
  // before `merge`/`save` runs, rather than leaving a half-applied publish with no word to the
  // reviewer.
  const applyEdits = async (e: CustomEvent): Promise<boolean> => {
    const ocdid = currentEntry?.jurisdiction?.ocdid;
    if (!ocdid || !changesetId) return true;
    const byPerson = new Map<string, any>();
    for (const person of e.detail.people ?? []) {
      byPerson.set(person.id, { id: person.id, fields: person.fields });
    }
    for (const change of (e.detail.officeEdits ?? []) as OfficeEdit[]) {
      const person = byPerson.get(change.personId) ?? { id: change.personId };
      person.offices = [{ id: change.postId, membership_label: change.membershipLabel }];
      byPerson.set(change.personId, person);
    }
    if (!byPerson.size) return true;
    try {
      await editJurisdictionRoster(ocdid, [...byPerson.values()], changesetId);
      return true;
    } catch (err: any) {
      window.alert(err.message ?? "Failed to save the card.");
      return false;
    }
  };

  // The card owns the reviewer's edits and hands them over when it asks to
  // publish or save; the page only decides what that does to the session.
  const handlePublish = async (e: CustomEvent) => {
    if (await applyEdits(e)) merge(e.detail.people);
  };
  const handleSave = async (e: CustomEvent) => {
    if (await applyEdits(e)) save(e.detail.people);
  };
  const handleNavigateTo = (e: CustomEvent) => navigateTo(e.detail.entry_number);

  const progress = reviewing
    ? {
        entryNumber: reviewing.entry_number,
        hasPrev: reviewing.entry_number > 1,
        resolvedEntryNumbers: reviewing.resolved_entry_numbers,
        savedEntryNumbers: reviewing.saved_entry_numbers,
        failedEntryNumbers: new Set(reviewing.failed_entries.keys()),
        frontierEntry: reviewing.frontier_entry,
        total: reviewing.total,
      }
    : null;

  // The publish error for the entry we're currently on (if its last publish was
  // rejected), shown as an in-place banner so the reviewer can fix and retry.
  const publishError = reviewing ? reviewing.failed_entries.get(reviewing.entry_number) ?? null : null;

  const renderBody = () => {
    if (fsm.kind === StateKind.LOADING) {
      return html`<main class="review-session page-content"><p>Loading...</p></main>`;
    }
    if (fsm.kind === StateKind.ERROR) {
      return html`<main class="review-session page-content">
        <p class="review-session__error">${fsm.message}</p>
        <a class="btn btn-sm" href=${landingUrl(stateCode)}>Back to review</a>
      </main>`;
    }
    return html`<review-session
      .currentEntry=${currentEntry}
      .hasSession=${session != null}
      .progress=${progress}
      .error=${publishError}
      .canReject=${permissions.can_reject_scrape}
      .canViewSourceDebug=${permissions.can_view_source_debug}
      .isRejecting=${isRejecting}
      .canAssignMembership=${canAssignMembership}
      .canCreatePost=${permissions.can_create_post}
      @back=${back}
      @advance=${advance}
      @navigate-to=${handleNavigateTo}
      @end-session=${endSession}
      @publish=${handlePublish}
      @save=${handleSave}
      @reject=${rejectScrape}
    ></review-session>`;
  };

  return html`
    ${renderBody()}
    <civ-review-log .entries=${reviewLogEntries}></civ-review-log>
  `;
}

customElements.define("review-session-page", component(ReviewSessionPage, { useShadowDOM: false }));
