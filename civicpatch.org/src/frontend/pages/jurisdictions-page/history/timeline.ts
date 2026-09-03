// One jurisdiction's history, as a page of its own.
//
// Two sections, because they answer different questions. "In progress" is what somebody still
// has to act on — short, unpaged, structurally bounded. "Past" is the complete record, paged.
// A pending changeset appears in both: the first as a thing to do, the second as a thing that
// happened. That is deliberate, not a duplicate to be filtered.

import { component, useState, useEffect } from "haunted";
import { useAuth } from "../../../hooks/useAuth.js";
import { html, nothing } from "lit-html";
// `.jurisdiction-section`, `.pr-row` and the page shell live there; this page reuses them
// rather than growing a second set that would drift from the jurisdiction page's.
import "../jurisdiction-page.css";
import "./timeline.css";
import "./timeline-entry.ts";
import { IN_PROGRESS_ANCHOR } from "./history-routes.js";
import type { InFlightEntry } from "../awaiting-review.js";
import "./scrape-in-progress.ts";
import { Pagination } from "../../../components/pagination/index.js";
import {
  cancelPipelineRun,
  fetchJurisdictionHistory,
  fetchJurisdictionInFlight,
} from "../../../api.js";
import { dateStringToFriendly } from "../../../utils/date-utils.js";
import { jurisdictionOcdidToState } from "../../../components/ocdid-utils.js";
import { LOGIN_PATH, reviewSessionUrl } from "../../review-routes.js";
import type { TimelineEntry } from "./timeline-entry.ts";

// Mirrors DEFAULT_HISTORY_LIMIT in database/jurisdictions.py.
const PER_PAGE = 25;

// How often to re-read while a cancel is outstanding. Cancelling asks Temporal to stop; the
// run ends when it ends, so the only way to know is to keep looking.
const CANCEL_POLL_MS = 4000;



// Haunted passes `observedAttributes` through verbatim, so these are the attribute names, not
// camelCase. Renaming them here silently yields undefined props and an empty page.
interface TimelineProps {
  jurisdiction_ocdid: string;
  jurisdiction_name: string;
}

function renderAwaiting(entry: InFlightEntry, ocdid: string, isSignedIn: boolean) {
  const href = isSignedIn
    ? reviewSessionUrl(jurisdictionOcdidToState(ocdid), entry.changeset_id)
    : LOGIN_PATH;

  return html`
    <div class="pr-row">
      <div class="pr-row__main">
        <span class="pr-row__title">
          ${entry.kind === "sheet_import" ? "Import" : "Scrape"} of
          ${dateStringToFriendly(entry.created_at ?? "")}
        </span>
        <span class="pr-row__sub">Awaiting review</span>
      </div>
      <span class="pr-row__actions">
        <a class="btn-primary" href=${href}>
          ${isSignedIn
              ? html`Review <i class="fa-solid fa-arrow-right"></i>`
              : "Sign in to review"}
        </a>
      </span>
    </div>
  `;
}

function CivTimeline({ jurisdiction_ocdid, jurisdiction_name }: TimelineProps) {
  // This page has no parent to pass permissions down, so it asks for its own — the same way
  // the jurisdiction page does. Public page: each action gates itself as they land.
  const { user, permissions } = useAuth();
  const isSignedIn = !!user?.authenticated;
  const isAdmin = !!permissions.can_view_temporal_workflow_state;
  const jurisdictionOcdid = jurisdiction_ocdid;
  const jurisdictionName = jurisdiction_name;
  const [entries, setEntries] = useState<TimelineEntry[]>([]);
  const [inFlight, setInFlight] = useState<InFlightEntry[]>([]);
  const [totalChangesets, setTotalChangesets] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [page, setPage] = useState(1);
  const [loadFailed, setLoadFailed] = useState(false);
  const [cancelRequested, setCancelRequested] = useState<string[]>([]);

  useEffect(() => {
    if (!jurisdictionOcdid) return;
    fetchJurisdictionHistory(jurisdictionOcdid, page, PER_PAGE)
      .then((body: any) => {
        setEntries(body.data ?? []);
        setTotalPages(body.total_pages ?? 1);
        setLoadFailed(false);
      })
      .catch(() => setLoadFailed(true));
  }, [jurisdictionOcdid, page]);

  const loadInFlight = () =>
    fetchJurisdictionInFlight(jurisdictionOcdid)
      .then((body: any) => {
        const rows: InFlightEntry[] = body.data?.in_flight ?? [];
        setInFlight(rows);
        setTotalChangesets(body.data?.total_changesets ?? 0);
        // Forget the ones the server has stopped, so the poll below can stand down.
        const live = new Set(rows.map((entry) => entry.changeset_id));
        setCancelRequested((prev) => prev.filter((id) => live.has(id)));
      })
      .catch(() => setInFlight([]));

  // Separate effect: the live section does not change when the reader turns a page.
  useEffect(() => {
    if (!jurisdictionOcdid) return;
    loadInFlight();
  }, [jurisdictionOcdid]);

  // The jurisdiction page used to "cancel" by rewriting its own copy of the row — the server
  // was never told, so the run carried on and the next load showed it still going. Ask the
  // API, and leave the row in place: it is a request, and the run is still going until it
  // is not.
  const handleCancel = async (changesetId: string) => {
    try {
      await cancelPipelineRun(changesetId);
    } catch (_) {
      // Leave the row untouched so the reader can retry rather than lose the button.
      return;
    }
    setCancelRequested((prev) => [...prev, changesetId]);
  };

  // Only while something is outstanding — a page with nothing cancelling polls nothing.
  useEffect(() => {
    if (!cancelRequested.length) return;
    const timer = setInterval(loadInFlight, CANCEL_POLL_MS);
    return () => clearInterval(timer);
  }, [cancelRequested.length, jurisdictionOcdid]);

  const running = inFlight.filter((entry) => entry.is_running);
  const awaiting = inFlight.filter((entry) => entry.awaiting_review);

  return html`
    <main class="jurisdiction-page page-content">
      <div class="jurisdiction-page__title-row">
        <div class="jurisdiction-page__heading">
          <h1 class="jurisdiction-page__h1">History</h1>
          <span class="jurisdiction-page__published">
            ${jurisdictionName}, ${totalChangesets}
            ${totalChangesets === 1 ? "changeset" : "changesets"}
          </span>
        </div>
      </div>

      <hr class="jurisdiction-page__hairline" />

      ${running.length || awaiting.length
        ? html`
            <section class="jurisdiction-section" id="${IN_PROGRESS_ANCHOR}">
              <h2 class="jurisdiction-section__title">In progress</h2>
              ${running.map(
                (entry) => html`<civ-scrape-in-progress
                  .scrape=${entry}
                  .canCancel=${permissions.can_cancel_pipeline_run}
                  .canViewTemporalWorkflowState=${permissions.can_view_temporal_workflow_state}
                  .onCancel=${handleCancel}
                  .cancelRequested=${cancelRequested.includes(entry.changeset_id)}
                  .temporalUrl=${null}
                ></civ-scrape-in-progress>`,
              )}
              <div class="pr-list">
                ${awaiting.map((entry) =>
                  renderAwaiting(entry, jurisdictionOcdid, isSignedIn),
                )}
              </div>
            </section>
          `
        : nothing}

      <section class="jurisdiction-section">
        <h2 class="jurisdiction-section__title">Past</h2>
        ${loadFailed
          ? html`<p class="tl-empty">That history could not be loaded.</p>`
          : entries.length
            ? html`
                ${entries.map(
                  (entry) => html`<civ-timeline-entry
                    .entry=${entry}
                    .isAdmin=${isAdmin}
                    .isSignedIn=${isSignedIn}
                    .jurisdictionOcdid=${jurisdictionOcdid}
                  ></civ-timeline-entry>`,
                )}
                ${totalPages > 1
                  ? Pagination({
                      page,
                      totalPages,
                      onPrevious: () => setPage(Math.max(1, page - 1)),
                      onNext: () => setPage(Math.min(totalPages, page + 1)),
                      // Fixed page size: `null` is what hides the per-page selector.
                      perPage: PER_PAGE,
                      onPerPageChange: null,
                    })
                  : nothing}
              `
            : html`<p class="tl-empty">
                Nothing has been scraped, imported or edited here yet.
              </p>`}
      </section>
    </main>
  `;
}

customElements.define(
  "civ-jurisdiction-history",
  component(CivTimeline as any, {
    useShadowDOM: false,
    observedAttributes: ["jurisdiction_ocdid", "jurisdiction_name"],
  }),
);
