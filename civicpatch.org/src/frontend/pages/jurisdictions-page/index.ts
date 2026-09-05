import { component, useState, useEffect } from "haunted";
import "../../components/posts-list/posts-list.js";
import { html, nothing } from "lit-html";
import { useWebSocket } from "../../hooks/use-websocket.js";
import { useAuth } from "../../hooks/useAuth.js";
import { usePeople } from "../../hooks/usePeople.js";
import { buildIdentitiesMap } from "../../utils/people.js";
import { jurisdictionOcdidToPath } from "../../components/ocdid-utils.js";
import { historyUrl } from "./history/history-routes.js";

import "./jurisdiction-page.css";
import "./jurisdiction-details.js";
import "./scrape-modal/scrape-modal.js";
import "./scrape-modal/name-config-form.js";

import { triggerPipelineRun, fetchJurisdictionInFlight, patchJurisdictionData } from "../../api.js";
import { renderJurisdictionHeader } from "./jurisdiction-header.js";
import "./roster-editor.js";
import {
  pendingReviews,
  peopleEditBlockers,
  jurisdictionEditBlockers,
  renderPendingReviews,
  editingBlockedReason,
  jurisdictionEditBlockedReason,
  IN_FLIGHT_ENTRY_TYPE,
  type InFlightEntry,
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
  // Only what is still in flight, plus two scalars. This used to fetch every changeset the
  // jurisdiction has ever had in order to derive four things from the array.
  const [inFlight, setInFlight] = useState<InFlightEntry[]>([]);
  const [publishedAtDate, setPublishedAtDate] = useState<string | null>(null);
  const [isTriggering, setIsTriggering] = useState(false);
  const [scrapeError, setScrapeError] = useState<string | null>(null);

  useEffect(() => {
    if (!jurisdiction_ocdid) return;
    fetchJurisdictionInFlight(jurisdiction_ocdid)
      .then((body: any) => {
        setInFlight(body.data?.in_flight ?? []);
        setPublishedAtDate(body.data?.last_published_at ?? null);
      })
      .catch(() => setInFlight([]));
  }, [jurisdiction_ocdid]);

  const wsTopic = jurisdiction_ocdid ? `pipeline_run_status:${jurisdiction_ocdid}` : null;
  const { data: pipelineRunStatus } = useWebSocket(wsTopic, {
    autoConnect: !!wsTopic,
  });

  const jurisdictionData = jurisdiction_data ? JSON.parse(jurisdiction_data) : null;
  const identities = buildIdentitiesMap(people);
  // Split rather than decorate: a scrape in flight is a different thing from one waiting on a
  // reviewer, and only the first has a progress bar to show.
  const liveEntry = inFlight.find((entry) => entry.is_running);
  const awaitingReview = pendingReviews(inFlight);
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
      // `result.changeset_id` is the run's id: POST /pipeline_runs still names its parameter
      // that, from before runs and changesets were separate rows.
      const newEntry = {
        id: result.changeset_id,
        entry_type: IN_FLIGHT_ENTRY_TYPE.PIPELINE_RUN,
        pipeline_run_status: result.status,
        pipeline_run_progress: 0,
        created_at: now,
        updated_at: now,
        change_url: null,
        branch_name: null,
        jurisdiction_ocdid,
      };
      setInFlight((prev: InFlightEntry[]) => [newEntry, ...prev]);
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

  // Both sources answer it themselves now — the socket payload and the in-flight row carry
  // `is_running`, so this no longer has to know which statuses are terminal.
  const isRunInProgress = pipelineRunStatus?.is_running ?? !!liveEntry;
  const historyHref = historyUrl(jurisdictionOcdidToPath(jurisdiction_ocdid));

  const canStartScrape =
    permissions.can_scrape;

  return html`
    <main class="jurisdiction-page page-content">
      ${renderJurisdictionHeader({
        name: jurisdictionData?.data?.name,
        ocdid: jurisdiction_ocdid,
        isScraped: people?.length > 0,
        hasUrl: !!jurisdictionData?.data?.url,
        publishedAt: publishedAtDate,
        historyHref,
        canStartScrape,
        isScrapeBlocked: peopleBlockers.length > 0,
        isRunInProgress: !!isRunInProgress || isTriggering,
        onScrapeClick: () => setScrapeModalOpen(true),
      })}

      ${renderDataFlag(jurisdictionData?.data)}
      ${scrapeError ? html`<p style="color: var(--pico-del-color);">${scrapeError}</p>` : nothing}

      ${renderPendingReviews(awaitingReview, jurisdiction_ocdid, isSignedIn)}

      <civ-roster-editor
        .people=${people}
        .jurisdictionOcdid=${jurisdiction_ocdid}
        .canEdit=${!!permissions.can_edit_jurisdiction_data && !peopleBlockers.length}
        .isLoading=${peopleLoading}
        .blockedReason=${editingBlockedReason(peopleBlockers)}
        .onPublished=${() => window.location.reload()}
      ></civ-roster-editor>

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
