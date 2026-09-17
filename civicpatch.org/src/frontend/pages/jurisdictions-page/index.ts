import { component, useState, useEffect } from "haunted";
import "../../components/organizations-list/organizations-list.js";
import "../../components/basic/modal.js";
import { html, nothing } from "lit-html";
import { useWebSocket } from "../../hooks/use-websocket.js";
import { useAuth } from "../../hooks/useAuth.js";
import { usePeople } from "../../hooks/usePeople.js";
import { jurisdictionOcdidToPath } from "../../components/ocdid-utils.js";
import { historyUrl } from "./history/history-routes.js";
import {
  SectionNav,
  jurisdictionSection,
} from "../../components/section-nav/index.js";
import { pipelineRunStatusChannel } from "../../schemas/pubsub-channels.js";

import "../../components/panel/panel.css";
import "./jurisdiction-page.css";
import "./jurisdiction-details.js";
import "./scrape-modal/scrape-modal.js";
import "./scrape-modal/name-config-form.js";

import {
  triggerPipelineRun,
  fetchJurisdictionInFlight,
  patchJurisdictionData,
} from "../../api.js";
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

// Issues nobody acts on from this page. A missing wikipedia link and a GEOID
// suffix-fallback match are both upstream matching noise, not something a
// maintainer fixes here, so surfacing them as a warning is pure cost. The
// GEOID case still explains itself — see the "Notes" row in the details panel.
const SUPPRESSED_ISSUES = new Set(["no_wiki_match", "geoid_mismatch"]);

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
      <i
        class="fa-solid fa-triangle-exclamation data-flag__icon"
        aria-hidden="true"
      ></i>
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
  canEditPermission: boolean,
  onSave: (form: any) => Promise<any>,
  blockedReason: string | null,
) {
  return html`
    <section class="panel">
      <civ-jurisdiction-details
        .data=${jurisdictionData?.data}
        .canEditPermission=${canEditPermission}
        .onSave=${onSave}
        .blockedReason=${blockedReason}
      ></civ-jurisdiction-details>
    </section>
  `;
}

function JurisdictionPage({
  jurisdiction_ocdid,
  jurisdiction_data,
}: JurisdictionPageProps) {
  // Public page — nothing waits on permissions; each action gates itself and
  // appears once they land.
  const { user, permissions } = useAuth();
  const isSignedIn = !!user?.authenticated;
  const { people, isLoading: peopleLoading, refetch: refetchPeople } = usePeople(jurisdiction_ocdid);
  const [scrapeModalOpen, setScrapeModalOpen] = useState(false);
  const [manageOrgsOpen, setManageOrgsOpen] = useState(false);
  const hasEditPermission = !!permissions.can_edit_jurisdiction_data;
  // Its own flag, not `hasEditPermission` reused — creating a post is a distinct capability
  // that happens to sit at the same tier today, not the same permission as editing the
  // jurisdiction's own published data.
  const canCreatePost = !!permissions.can_create_post;
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

  const wsTopic = jurisdiction_ocdid
    ? pipelineRunStatusChannel(jurisdiction_ocdid)
    : null;
  const { data: pipelineRunStatus } = useWebSocket(wsTopic, {
    autoConnect: !!wsTopic,
  });

  const jurisdictionData = jurisdiction_data
    ? JSON.parse(jurisdiction_data)
    : null;
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
      const newEntry = {
        id: result.pipeline_run_id,
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

  const canStartScrape = permissions.can_scrape;

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
        canManageOrganizations: !!permissions.can_manage_organizations,
        onManageOrganizationsClick: () => setManageOrgsOpen(true),
      })}
      ${renderDataFlag(jurisdictionData?.data)}
      ${scrapeError
        ? html`<p style="color: var(--diff-removed);">${scrapeError}</p>`
        : nothing}

      <div class="sectioned">
        ${SectionNav(
          "jurisdiction",
          jurisdictionSection(
            jurisdictionOcdidToPath(jurisdiction_ocdid),
            historyHref,
          ),
          `/${jurisdictionOcdidToPath(jurisdiction_ocdid)}`,
        )}
        <div class="secbody">
          <div class="jurisdiction-page__cols">
            <div>
              ${renderDetailsSection(
                jurisdictionData,
                hasEditPermission && !jurisdictionBlockers.length,
                handleJurisdictionSave,
                jurisdictionEditBlockedReason(jurisdictionBlockers),
              )}
            </div>
            <div class="jurisdiction-page__col-main">
              ${renderPendingReviews(
                awaitingReview,
                jurisdiction_ocdid,
                isSignedIn,
              )}

              <civ-roster-editor
                .people=${people}
                .jurisdictionOcdid=${jurisdiction_ocdid}
                .canEdit=${hasEditPermission && !peopleBlockers.length}
                .canAssignMembership=${hasEditPermission && !peopleBlockers.length}
                .canCreatePost=${canCreatePost && !peopleBlockers.length}
                .isLoading=${peopleLoading}
                .blockedReason=${editingBlockedReason(peopleBlockers)}
                .onPublished=${refetchPeople}
              ></civ-roster-editor>
            </div>
          </div>
        </div>
      </div>

      ${jurisdictionData
        ? html`<civ-scrape-modal
            .onStartScrape=${handleScrapeStartClick}
            .url=${jurisdictionData?.data?.url}
            .modalProps=${{
              open: scrapeModalOpen,
              onClose: () => setScrapeModalOpen(false),
              closeOnBackdropClick: true,
            }}
          ></civ-scrape-modal>`
        : nothing}

      <civ-modal
        .title=${"Manage organizations"}
        .content=${html`<civ-organizations-list
          .jurisdictionOcdid=${jurisdiction_ocdid}
          .canManage=${!!permissions.can_manage_organizations}
        ></civ-organizations-list>`}
        .modalProps=${{ open: manageOrgsOpen, onClose: () => setManageOrgsOpen(false) }}
      ></civ-modal>
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
