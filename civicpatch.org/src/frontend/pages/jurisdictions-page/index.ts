import { component, useState, useEffect } from "haunted";
import { html, nothing } from "lit-html";
import { useWebSocket } from "../../hooks/use-websocket.js";
import { useAuth } from "../../hooks/useAuth.js";
import { usePeople } from "../../hooks/usePeople.js";
import { buildIdentitiesMap } from "../../utils/people.js";
import { dateStringToFriendly } from "../../utils/date-utils.js";
import "./jurisdiction-page.css";
import "./history/history-list.js";
import "./jurisdiction-details.js";
import "./scrape-modal/scrape-modal.js";
import "./scrape-modal/name-config-form.js";

import { triggerPipelineRun, fetchJurisdictionHistory, patchJurisdictionData } from "../../api.js";
import { TERMINAL_JOB_STATUSES } from "../../components/job-status.js";
import { renderJurisdictionHeader } from "./jurisdiction-header.js";
import "./officials-editor.js";
import {
  openPullRequests,
  peopleEditBlockers,
  jurisdictionEditBlockers,
  renderOpenPullRequests,
  editingBlockedReason,
  jurisdictionEditBlockedReason,
  type HistoryEntry,
} from "./open-pull-requests.js";

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
  const { permissions } = useAuth();
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

  const wsTopic = jurisdiction_ocdid ? `job_status:${jurisdiction_ocdid}` : null;
  const { data: jobStatus, isConnected, error: sseError } = useWebSocket(wsTopic, {
    autoConnect: !!wsTopic,
  });

  const jurisdictionData = jurisdiction_data ? JSON.parse(jurisdiction_data) : null;
  const identities = buildIdentitiesMap(people);
  const entries: HistoryEntry[] = history?.data ?? [];
  const openPrs = openPullRequests(entries);
  // Blocked independently: each kind only locks the file it already has in flight.
  const peopleBlockers = peopleEditBlockers(openPrs);
  const jurisdictionBlockers = jurisdictionEditBlockers(openPrs);

  const handleScrapeStartClick = async (details: any) => {
    setScrapeModalOpen(false);
    setIsTriggering(true);
    setScrapeError(null);
    try {
      const result = await triggerPipelineRun(
        details.scrapeMode,
        jurisdictionData.data.id,
        jurisdictionData.data.name,
        details.data.url || jurisdictionData.data.url,
        details.data.sourceUrls,
      );
      const now = new Date().toISOString();
      const newEntry = {
        request_id: result.request_id,
        job_status: result.status,
        job_progress: 0,
        created_at: now,
        updated_at: now,
        pull_request_url: null,
        pull_request_status: null,
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

  const handleCancelJob = (requestId: string) => {
    setHistory((prev: any) => ({
      ...prev,
      data: prev.data.map((j: any) =>
        j.request_id === requestId ? { ...j, job_status: "CANCELLED" } : j,
      ),
    }));
  };

  // The currently-published data: the most recent successful run (merged runs are
  // SUCCESS too). Same date shown in the history rows.
  const publishedAt = entries.find(
    (j: any) => (j.job_status || "").toUpperCase() === "SUCCESS",
  )?.created_at;

  const mostRecentJob: any = entries[0];
  const effectiveStatus =
    jobStatus && mostRecentJob && jobStatus.request_id === mostRecentJob.request_id
      ? jobStatus.status
      : mostRecentJob?.job_status;
  const isJobRunning =
    (jobStatus && !TERMINAL_JOB_STATUSES.has(jobStatus.status)) ||
    (!!effectiveStatus && !TERMINAL_JOB_STATUSES.has(effectiveStatus));

  const canStartScrape =
    permissions.can_scrape_remote || permissions.can_scrape_local;

  return html`
    <main class="jurisdiction-page page-content">
      ${renderJurisdictionHeader({
        name: jurisdictionData?.data?.name,
        ocdid: jurisdiction_ocdid,
        isScraped: people?.length > 0,
        publishedAt,
        canStartScrape,
        isScrapeBlocked: peopleBlockers.length > 0,
        isJobRunning: !!isJobRunning || isTriggering,
        onScrapeClick: () => setScrapeModalOpen(true),
      })}

      ${renderDataFlag(jurisdictionData?.data)}
      ${scrapeError ? html`<p style="color: var(--pico-del-color);">${scrapeError}</p>` : nothing}

      ${renderOpenPullRequests(openPrs, jurisdiction_ocdid)}

      <civ-officials-editor
        .people=${people}
        .jurisdictionOcdid=${jurisdiction_ocdid}
        .canEdit=${!!permissions.can_edit_jurisdiction_data && !peopleBlockers.length}
        .isLoading=${peopleLoading}
        .blockedReason=${editingBlockedReason(peopleBlockers)}
        .onPublished=${() => window.location.reload()}
      ></civ-officials-editor>

      ${renderDetailsSection(
        jurisdictionData,
        !!permissions.can_edit_jurisdiction_data && !jurisdictionBlockers.length,
        handleJurisdictionSave,
        jurisdictionEditBlockedReason(jurisdictionBlockers),
      )}

      <details class="jurisdiction-panel" ?open=${!!isJobRunning}>
        <summary>
          Scrape history
          <span class="jurisdiction-panel__meta">
            ${entries.length} ${entries.length === 1 ? "run" : "runs"}
            ${publishedAt ? `· last ${dateStringToFriendly(publishedAt)}` : ""}
          </span>
        </summary>
        <div class="jurisdiction-panel__body">
          <civ-history-list
            .history=${history}
            .jobStatus=${jobStatus}
            .isConnected=${isConnected}
            .sseError=${sseError}
            .canCancel=${permissions.can_cancel_job}
            .onCancel=${handleCancelJob}
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
            .canScrapeRemote=${permissions.can_scrape_remote}
            .canScrapeLocal=${permissions.can_scrape_local}
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
