import { component, useState, useEffect } from "haunted";
import { html } from "lit-html";
import { useWebSocket } from "../../hooks/use-websocket.js";
import { useAuth } from "../../hooks/useAuth.js";
import { usePeople } from "../../hooks/usePeople.js";
import { buildIdentitiesMap } from "../../utils/people.js";
import "../../components/edit-people/edit-people.js";
import "./history/history-list.js";
import "./jurisdiction-header.js";
import "./jurisdiction-sidebar.js";
import "./scrape-modal/scrape-modal.js";
import "./scrape-modal/name-config-form.js";

import { triggerPipelineRun, fetchJurisdictionHistory, patchJurisdictionData } from '../../api.js';
import { TERMINAL_JOB_STATUSES } from '../../components/job-status.js';

function JurisdictionPage({ jurisdiction_ocdid, jurisdiction_data }) {
  const { loading: authLoading, permissions } = useAuth();
  const { people, isLoading: peopleLoading } = usePeople(jurisdiction_ocdid);
  const [scrapeModalOpen, setScrapeModalOpen] = useState(false);
  const [history, setHistory] = useState(null);
  const [isTriggering, setIsTriggering] = useState(false);

  useEffect(() => {
    if (!jurisdiction_ocdid) return;
    fetchJurisdictionHistory(jurisdiction_ocdid)
      .then(setHistory)
      .catch(() => setHistory(null));
  }, [jurisdiction_ocdid]);

  // Guards after all hooks (hooks must not be called conditionally)
  if (authLoading) {
    return html`<p>Checking authentication...</p>`;
  }
  if (!permissions.JURISDICTION_PAGE) {
    return html`<p>You must be logged in to view this page.</p>`;
  }

  const jurisdictionData = jurisdiction_data ? JSON.parse(jurisdiction_data) : null;
  const identities = buildIdentitiesMap(people);

  const wsTopic = jurisdiction_ocdid ? `job_status:${jurisdiction_ocdid}` : null;

  const { data: jobStatus, isConnected, error: sseError } = useWebSocket(wsTopic, {
    autoConnect: !!wsTopic,
  });

  const handleScrapeStartClick = async (details) => {
    setScrapeModalOpen(false);
    setIsTriggering(true);
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
      jurisdiction_ocdid: jurisdiction_ocdid,
    };
    setHistory(prev => ({ ...prev, data: [newEntry, ...(prev?.data ?? [])] }));
  };

  const handleJurisdictionSave = async (formData) => {
    const result = await patchJurisdictionData(jurisdiction_ocdid, formData);
    return result.data;
  };

  const handleCancelJob = (requestId) => {
    setHistory(prev => ({
      ...prev,
      data: prev.data.map(j => j.request_id === requestId ? { ...j, job_status: "CANCELLED" } : j),
    }));
  };

  const scrapeStatus = people?.length > 0 ? "Scraped" : "Unscraped";
  const canStartScrape = permissions.JURISDICTION_PAGE_SCRAPE_REMOTE || permissions.JURISDICTION_PAGE_SCRAPE_LOCAL;
  // Date of the currently-published data: the most recent successful run
  // (covers merged runs too — they're SUCCESS). Same date shown in the history rows.
  const publishedAt = history?.data?.find(
    j => (j.job_status || "").toUpperCase() === "SUCCESS"
  )?.created_at;

  const mostRecentJob = history?.data?.[0];
  const effectiveStatus = (jobStatus && mostRecentJob && jobStatus.request_id === mostRecentJob.request_id)
    ? jobStatus.status
    : mostRecentJob?.job_status;
  const isJobRunning = (jobStatus && !TERMINAL_JOB_STATUSES.has(jobStatus.status))
    || (!!effectiveStatus && !TERMINAL_JOB_STATUSES.has(effectiveStatus));

  return html`
    <div class="jurisdictions-page page-content" style="display: flex; flex-direction: column; gap: 2rem;">
      <div class="grid">
        <div style="display: flex; flex-direction: column; gap: 2rem;">
          <civ-map
            canmove="false"
            .latlng=${jurisdictionData?.geo_center
              ? { lat: jurisdictionData.geo_center.lat, lng: jurisdictionData.geo_center.lng }
              : null}
            .height=${"20rem"}
          ></civ-map>
          <civ-history-list
            .history=${history}
            .jobStatus=${jobStatus}
            .isConnected=${isConnected}
            .sseError=${sseError}
            .canCancel=${permissions.CANCEL_JOB}
            .onCancel=${handleCancelJob}
          ></civ-history-list>
        </div>

        <div>
          <civ-jurisdiction-header
            .name=${jurisdictionData?.data?.name}
            .scrapeStatus=${scrapeStatus}
            .publishedAt=${publishedAt}
            .details=${jurisdictionData}
            .ocdid=${jurisdiction_ocdid}
          ></civ-jurisdiction-header>

          <hr />

          <civ-jurisdiction-sidebar
            .jurisdictionData=${jurisdictionData}
            .onScrapeClick=${() => setScrapeModalOpen(true)}
            .canStartScrape=${canStartScrape}
            .isJobRunning=${isJobRunning || isTriggering}
            .onSave=${handleJurisdictionSave}
          ></civ-jurisdiction-sidebar>

          ${jurisdictionData ? html`
            <civ-scrape-modal
              .onStartScrape=${handleScrapeStartClick}
              .url=${jurisdictionData?.data?.url}
              .modalProps=${{
                open: scrapeModalOpen,
                onClose: () => setScrapeModalOpen(false),
                closeOnBackdropClick: true
              }}
              .identities=${identities}
              .canScrapeRemote=${permissions.JURISDICTION_PAGE_SCRAPE_REMOTE}
              .canScrapeLocal=${permissions.JURISDICTION_PAGE_SCRAPE_LOCAL}
            ></civ-scrape-modal>
          ` : null}

        </div>
      </div>

      ${!peopleLoading ? html`
        <civ-editable-people-list
          jurisdiction_ocdid=${jurisdiction_ocdid}
          .people=${people}
          .canDeletePeople=${permissions.DIRECTORY_DELETE}
          .canClosePr=${permissions.PR_CLOSE}
          .onPublished=${() => window.location.reload()}
        ></civ-editable-people-list>
      ` : null}
    </div>
  `;
}

customElements.define(
  "civ-jurisdiction-page",
  component(JurisdictionPage, {
    useShadowDOM: false,
    observedAttributes: ["jurisdiction_ocdid", "jurisdiction_data"],
  }),
);
