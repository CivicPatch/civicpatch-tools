import { component, useState, useEffect } from "haunted";
import "../../components/posts-list/posts-list.js";
import { html, nothing } from "lit-html";
import { useWebSocket } from "../../hooks/use-websocket.js";
import { useAuth } from "../../hooks/useAuth.js";
import { usePeople } from "../../hooks/usePeople.js";
import { buildIdentitiesMap } from "../../utils/people.js";
import { dateStringToFriendly } from "../../utils/date-utils.js";
import "./jurisdiction-page.css";
import "./history/history-list.js";
import "./jurisdiction-details.js";
import "./history/scrape-in-progress.ts";
import "./scrape-modal/scrape-modal.js";
import "./scrape-modal/name-config-form.js";

import { triggerPipelineRun, fetchJurisdictionHistory, patchJurisdictionData } from "../../api.js";
import { renderJurisdictionHeader } from "./jurisdiction-header.js";
import "./officials-editor.js";
import {
  publishedAt,
  pendingReviews,
  peopleEditBlockers,
  jurisdictionEditBlockers,
  renderPendingReviews,
  editingBlockedReason,
  jurisdictionEditBlockedReason,
  type HistoryEntry,
} from "./awaiting-review.js";

interface JurisdictionPageProps {
  jurisdiction_ocdid: string;
  jurisdiction_data: string;
}

// Issues nobody acts on from this page. A missing wikipedia link is upstream
// matching noise, not something a maintainer fixes here — and it is 92 of the
// 2,499 flags in the dev data, so surfacing it is pure cost.
const SUPPRESSED_ISSUES = new Set(["no_wiki_match"]);

// data.issues names a problem the scrape already detected; generated_comments
// explains it. Neither has ever been rendered, so both surface here.
function renderDataFlag(data: any) {
  const issues: string[] = (data?.issues ?? []).filter(
    (issue: string) => !SUPPRESSED_ISSUES.has(issue),
  );
  if (!issues.length) return nothing;
  const title = issues.map((issue) => issue.replace(/_/g, " ")).join(", ");

  return html`
    <div class="data-flag">
      <i class="fa-solid fa-triangle-exclamation data-flag__icon" aria-hidden="true"></i>
      <div>
        <p class="data-flag__title">${title}</p>
        ${data?.generated_comments
          ? html`<p class="data-flag__body">${data.generated_comments}</p>`
          : nothing}
      </div>
    </div>
  `;
}

// A section, not a disclosure: this is what the record *is*, so it is always on
// screen. Only scrape history — an archive — stays collapsible.
function renderDetailsSection(
  jurisdictionData: any,
  canEdit: boolean,
  onSave: (form: any) => Promise<any>,
  blockedReason: string | null,
) {
  const data = jurisdictionData?.data;

  return html`
    <section class="jurisdiction-section">
      <div class="jurisdiction-section__head">
        <h2 class="jurisdiction-section__title">Jurisdiction details</h2>
      </div>
      ${blockedReason
        ? html`<p class="jurisdiction-section__blocked">
            <i class="fa-solid fa-lock" aria-hidden="true"></i> ${blockedReason}
          </p>`
        : nothing}
      <div class="jurisdiction-details">
        <civ-jurisdiction-details
          .data=${data}
          .canEdit=${canEdit}
          .onSave=${onSave}
        ></civ-jurisdiction-details>
        <civ-map
          canmove="false"
          .latlng=${jurisdictionData?.geo_center
            ? { lat: jurisdictionData.geo_center.lat, lng: jurisdictionData.geo_center.lng }
            : null}
          .height=${"9rem"}
        ></civ-map>
      </div>
    </section>
  `;
}

function JurisdictionPage({ jurisdiction_ocdid, jurisdiction_data }: JurisdictionPageProps) {
  // Public page — nothing waits on permissions; each action gates itself and
  // appears once they land.
  const { user, permissions } = useAuth();
  const isSignedIn = !!user?.authenticated;
  const { people, isLoading: peopleLoading } = usePeople(jurisdiction_ocdid);
  const [scrapeModalOpen, setScrapeModalOpen] = useState(false);
  const [history, setHistory] = useState<{ data: HistoryEntry[] } | null>(null);
  const [isTriggering, setIsTriggering] = useState(false);
  const [scrapeError, setScrapeError] = useState<string | null>(null);

  useEffect(() => {
    if (!jurisdiction_ocdid) return;
    fetchJurisdictionHistory(jurisdiction_ocdid)
      .then(setHistory)
      .catch(() => setHistory(null));
  }, [jurisdiction_ocdid]);

  const wsTopic = jurisdiction_ocdid ? `pipeline_run_status:${jurisdiction_ocdid}` : null;
  const { data: pipelineRunStatus, isConnected, error: sseError } = useWebSocket(wsTopic, {
    autoConnect: !!wsTopic,
  });

  const jurisdictionData = jurisdiction_data ? JSON.parse(jurisdiction_data) : null;
  const identities = buildIdentitiesMap(people);
  const entries: HistoryEntry[] = history?.data ?? [];
  // Split rather than decorate: a scrape in flight is a different thing from one that has
  // run, and the archive row for it would carry a meaningless percentage bar.
  const liveEntry = entries.find((entry) => entry.is_running);
  const pastEntries = entries.filter((e: any) => e !== liveEntry);
  const awaitingReview = pendingReviews(entries);
  // Blocked independently: each kind only locks the file it already has in flight.
  const peopleBlockers = peopleEditBlockers(awaitingReview);
  const jurisdictionBlockers = jurisdictionEditBlockers(awaitingReview);

  const handleScrapeStartClick = async (details: any) => {
    setScrapeModalOpen(false);
    setIsTriggering(true);
    setScrapeError(null);
    try {
      const result = await triggerPipelineRun(
        jurisdictionData.data.id,
        jurisdictionData.data.name,
        details.data.url || jurisdictionData.data.url,
        details.data.sourceUrls,
      );
      const now = new Date().toISOString();
      const newEntry = {
        changeset_id: result.changeset_id,
        pipeline_run_status: result.status,
        pipeline_run_progress: 0,
        created_at: now,
        updated_at: now,
        change_url: null,
        review_status: null,
        branch_name: null,
        jurisdiction_ocdid,
      };
      setHistory((prev: any) => ({ ...prev, data: [newEntry, ...(prev?.data ?? [])] }));
    } catch (err: any) {
      setScrapeError(err.message);
    } finally {
      setIsTriggering(false);
    }
  };

  const handleJurisdictionSave = async (formData: any) => {
    const result = await patchJurisdictionData(jurisdiction_ocdid, formData);
    return result.data;
  };

  const handleCancelRun = (changesetId: string) => {
    setHistory((prev: any) => ({
      ...prev,
      data: prev.data.map((j: any) =>
        j.changeset_id === changesetId ? { ...j, pipeline_run_status: "CANCELLED" } : j,
      ),
    }));
  };

  const publishedAtDate = publishedAt(entries);

  // null until the reader touches it, then it is theirs. Binding ?open straight to the run
  // state made cancelling slam the panel shut: the run goes terminal and lit closes it.
  const [userOpenedScrapes, setScrapesPanelOpen] = useState<boolean | null>(null);

  // Both sources answer it themselves now — the socket payload and the history row carry
  // `is_running`, so this no longer has to know which statuses are terminal.
  const isRunInProgress = pipelineRunStatus?.is_running ?? !!liveEntry;

  const scrapesPanelOpen = userOpenedScrapes ?? !!isRunInProgress;

  const canStartScrape =
    permissions.can_scrape;

  return html`
    <main class="jurisdiction-page page-content">
      ${renderJurisdictionHeader({
        name: jurisdictionData?.data?.name,
        ocdid: jurisdiction_ocdid,
        isScraped: people?.length > 0,
        publishedAt: publishedAtDate,
        canStartScrape,
        isScrapeBlocked: peopleBlockers.length > 0,
        isRunInProgress: !!isRunInProgress || isTriggering,
        onScrapeClick: () => setScrapeModalOpen(true),
      })}

      ${renderDataFlag(jurisdictionData?.data)}
      ${scrapeError ? html`<p style="color: var(--pico-del-color);">${scrapeError}</p>` : nothing}

      ${renderPendingReviews(awaitingReview, jurisdiction_ocdid, isSignedIn)}

      <civ-officials-editor
        .people=${people}
        .jurisdictionOcdid=${jurisdiction_ocdid}
        .canEdit=${!!permissions.can_edit_jurisdiction_data && !peopleBlockers.length}
        .isLoading=${peopleLoading}
        .blockedReason=${editingBlockedReason(peopleBlockers)}
        .onPublished=${() => window.location.reload()}
      ></civ-officials-editor>

      <section class="jurisdiction-section">
        <h2>Posts</h2>
        <civ-posts-list
          .jurisdictionOcdid=${jurisdiction_ocdid}
          .canEdit=${!!permissions.can_edit_jurisdiction_data && !peopleBlockers.length}
        ></civ-posts-list>
      </section>

      ${renderDetailsSection(
        jurisdictionData,
        !!permissions.can_edit_jurisdiction_data && !jurisdictionBlockers.length,
        handleJurisdictionSave,
        jurisdictionEditBlockedReason(jurisdictionBlockers),
      )}

      <details
        class="jurisdiction-panel"
        ?open=${scrapesPanelOpen}
        @toggle=${(e: Event) => setScrapesPanelOpen((e.target as HTMLDetailsElement).open)}
      >
        <summary>
          Scrapes
          <span class="jurisdiction-panel__meta">
            ${entries.length} ${entries.length === 1 ? "run" : "runs"}
            ${publishedAtDate ? `— last ${dateStringToFriendly(publishedAtDate)}` : ""}
          </span>
        </summary>
        <div class="jurisdiction-panel__body">
          ${liveEntry
            ? html`<civ-scrape-in-progress
                .scrape=${liveEntry}
                .canCancel=${permissions.can_cancel_pipeline_run}
                .canViewTemporalWorkflowState=${permissions.can_view_temporal_workflow_state}
                .onCancel=${handleCancelRun}
                .temporalUrl=${null}
              ></civ-scrape-in-progress>`
            : null}
          <civ-history-list
            .history=${{ data: pastEntries }}
            .pipelineRunStatus=${pipelineRunStatus}
            .isConnected=${isConnected}
            .sseError=${sseError}
            .canCancel=${permissions.can_cancel_pipeline_run}
            .isSignedIn=${isSignedIn}
            .onCancel=${handleCancelRun}
          ></civ-history-list>
        </div>
      </details>

      ${jurisdictionData
        ? html`<civ-scrape-modal
            .onStartScrape=${handleScrapeStartClick}
            .url=${jurisdictionData?.data?.url}
            .modalProps=${{
              open: scrapeModalOpen,
              onClose: () => setScrapeModalOpen(false),
              closeOnBackdropClick: true,
            }}
            .identities=${identities}
          ></civ-scrape-modal>`
        : nothing}
    </main>
  `;
}

customElements.define(
  "civ-jurisdiction-page",
  component(JurisdictionPage as any, {
    useShadowDOM: false,
    observedAttributes: ["jurisdiction_ocdid", "jurisdiction_data"],
  }),
);
