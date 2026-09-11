import "./home-page.css";
import "../../components/panel/panel.css";
import { component, useState, useEffect } from "haunted";
import { html } from "lit-html";
import { fetchPeople, fetchDashboard, fetchMapsCoverage } from "../../api.js";
import { useAuth } from "../../hooks/useAuth.js";
import "../../components/badge/badge.js";
import "../../components/leaderboard/index.js";
import "../../components/select-state/select-state.js";
import "../../components/progress-dashboard/locality-gaps.js";
import "../../components/people-directory/people-directory.ts";
import "../../components/map/browse-map.ts";
import { renderFreshnessWidget } from "../../components/progress-dashboard/freshness-widget.ts";
import "../../components/jurisdiction-search/jurisdiction-search.ts";
import { jurisdictionOcdidToPath } from "../../components/ocdid-utils.js";
import { useStateCoverage } from "./use-state-coverage.ts";
import { useReviewProgress } from "./use-review-progress.ts";
import { useRecentPublications } from "./use-recent-publications.ts";
import { renderRecentPublications } from "./recent-publications.ts";
import { renderCoverageByState } from "./coverage-by-state.ts";
import { useBlogUpdates } from "./use-blog-updates.ts";
import { renderBlogUpdates } from "./blog-updates.ts";

// A handful of recognizable towns across different states, each confirmed to already
// have a published roster — a chip that returns nothing undercuts the point of showing one.
const EXAMPLE_LOCATIONS = [
  "Seattle, WA",
  "Austin, TX",
  "Boston, MA",
  "San Francisco, CA",
];

function HomePage() {
  const { user, permissions } = useAuth();
  const [selectedState, setSelectedState] = useState("");
  const [selectedJurisdictionOcdid, setSelectedJurisdictionOcdid] =
    useState(null);
  const [selectedCountyOcdid, setSelectedCountyOcdid] = useState(null);
  const [exampleQuery, setExampleQuery] = useState("");
  const [people, setPeople] = useState([]);
  const [dashboardData, setDashboardData] = useState(null);
  const [coverageSummary, setCoverageSummary] = useState({});
  const { localStatus, toReviewCount } = useStateCoverage(selectedState);
  const { reviewStats, activeSession } = useReviewProgress(user, selectedState);
  const { recentPublications } = useRecentPublications();
  const { blogUpdates } = useBlogUpdates();

  useEffect(() => {
    if (!selectedJurisdictionOcdid) {
      setPeople([]);
      return;
    }
    fetchPeople(selectedJurisdictionOcdid).then((data) => setPeople(data.data));
  }, [selectedJurisdictionOcdid]);

  useEffect(() => {
    fetchDashboard().then((data) => setDashboardData(data.data));
  }, []);

  useEffect(() => {
    fetchMapsCoverage()
      .then((data) => setCoverageSummary(data.data ?? {}))
      .catch(() => {});
  }, []);

  useEffect(() => {
    const handler = (e) =>
      setSelectedState((e.detail.state || "").toLowerCase());
    document.addEventListener("state-select", handler);
    return () => document.removeEventListener("state-select", handler);
  }, []);

  const handleStateChange = (event) => {
    setSelectedState((event.detail.state || "").toLowerCase());
    setSelectedCountyOcdid(null);
    setSelectedJurisdictionOcdid(null);
  };

  const handleCoverageStateSelect = (stateCode) =>
    handleStateChange({ detail: { state: stateCode } });

  const handleCountyChange = (event) => {
    setSelectedCountyOcdid(event.detail.jurisdiction_ocdid);
    setSelectedJurisdictionOcdid(null);
  };

  // Map clicks stay exploratory — they fill the directory preview below rather than
  // leaving the page, since browsing the map is a different intent than search.
  const handleSelectJurisdictionChange = (event) => {
    setSelectedJurisdictionOcdid(event.detail.jurisdiction_ocdid);
  };

  // A search hit is a deliberate pick, not a browse — it navigates straight to the
  // jurisdiction's own page rather than previewing it in place.
  const handleSearchSelect = (event) => {
    window.location.href = `/${jurisdictionOcdidToPath(event.detail.jurisdiction_ocdid)}`;
  };

  return html`
    <div class="home-page">
      <div class="home-page__grid home-page__grid--3col">
        <div class="home-page__select-col">
          <div class="panel home-page__finder">
            <div class="panel__cap"><b>search</b></div>

            <div class="home-page__finder-search">
              <div class="home-page__example-chips">
                ${EXAMPLE_LOCATIONS.map(
                  (location) => html`
                    <button
                      type="button"
                      class="civ-badge civ-badge--secondary"
                      @click=${() => setExampleQuery(location)}
                    >
                      ${location}
                    </button>
                  `,
                )}
              </div>

              <civ-jurisdiction-search
                .seedQuery=${exampleQuery}
                @jurisdiction-select=${handleSearchSelect}
              ></civ-jurisdiction-search>
            </div>

            <div class="home-page__finder-divider"><span>or</span></div>

            <div class="home-page__finder-browse">
              <civ-select-state
                .selected=${selectedState}
                @state-change=${handleStateChange}
              ></civ-select-state>

              ${selectedState && dashboardData?.states?.[selectedState]
                ? html`
                    <a
                      class="home-page__browse-link"
                      href="/${selectedState}/local"
                    >
                      Browse
                      ${dashboardData.states[selectedState].civicpatch
                        .localities.known}
                      municipalities <i class="fa-solid fa-arrow-right"></i>
                    </a>
                  `
                : html`
                    <span
                      class="home-page__browse-link home-page__browse-link--disabled"
                      aria-disabled="true"
                    >
                      Browse <i class="fa-solid fa-arrow-right"></i>
                    </span>
                  `}
            </div>
          </div>

          ${renderCoverageByState({
            statesData: dashboardData?.states ?? {},
            onSelectState: handleCoverageStateSelect,
            selectedState,
            isLoggedIn: !!user,
            toReviewCount: user
              ? (reviewStats?.available_count ?? 0)
              : toReviewCount,
            hasActiveSession: activeSession != null,
          })}
        </div>

        ${user
          ? html`
              <div class="home-page__second-col">
                <browse-map
                  .state=${selectedState || ""}
                  .selectedOcdid=${selectedJurisdictionOcdid || ""}
                  .localStatus=${localStatus}
                  .coverageSummary=${coverageSummary}
                  @on-jurisdiction-change=${handleSelectJurisdictionChange}
                  @on-state-change=${handleStateChange}
                  @on-county-change=${handleCountyChange}
                ></browse-map>
                ${selectedState
                  ? renderFreshnessWidget({
                      stats: dashboardData,
                      state: selectedState,
                    })
                  : ""}
                ${renderRecentPublications({
                  publications: recentPublications,
                  canViewProfiles: !!permissions?.can_manage_roles,
                })}
              </div>
            `
          : html`
              <div class="home-page__second-col">
                ${renderRecentPublications({
                  publications: recentPublications,
                  canViewProfiles: !!permissions?.can_manage_roles,
                })}
              </div>
            `}

        <div class="home-page__third-col">
          ${renderBlogUpdates({ updates: blogUpdates })}
        </div>
      </div>

      <div class="home-page__below">
        <civ-people-directory
          .local=${people}
          .jurisdictionSelected=${!!selectedJurisdictionOcdid}
        ></civ-people-directory>
      </div>
    </div>
  `;
}

customElements.define(
  "home-page",
  component(HomePage, {
    useShadowDOM: false,
    observedAttributes: [],
  }),
);
