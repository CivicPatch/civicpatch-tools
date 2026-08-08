import "./home-page.css";
import { component, useState, useEffect } from "haunted";
import { html } from "lit-html";
import { fetchPeople, fetchDashboard, fetchMapsCoverage } from "../../api.js";
import {
  useLocalStorage,
  PERSIST_FOREVER,
} from "../../hooks/use-local-storage.js";
import { STORAGE_KEYS } from "../../utils/storage-keys.js";
import { useAuth } from "../../hooks/useAuth.js";
import "../../components/badge/badge.js";
import "../../components/leaderboard/index.js";
import "../../components/progress-dashboard/locality-gaps.js";
import "../../components/people-directory/people-directory.ts";
import "../../components/map/browse-map.ts";
import "../../components/verify-cta/verify-cta.ts";
import { renderContributionCard } from "../../components/contribution-card/contribution-card.ts";
import { renderFreshnessWidget } from "../../components/progress-dashboard/freshness-widget.ts";
import "../../components/jurisdiction-search/jurisdiction-search.ts";
import "../../components/jurisdiction-modal/jurisdiction-modal.ts";
import { useJurisdictionModal } from "./use-jurisdiction-modal.ts";
import { useStateCoverage } from "./use-state-coverage.ts";
import { useReviewProgress } from "./use-review-progress.ts";

function HomePage() {
  const { user, permissions } = useAuth();
  const [defaultState] = useLocalStorage(STORAGE_KEYS.DEFAULT_STATE, "", {
    ttl: PERSIST_FOREVER,
  });
  const [selectedState, setSelectedState] = useState(
    (defaultState || "").toLowerCase(),
  );
  const [selectedJurisdictionOcdid, setSelectedJurisdictionOcdid] =
    useState(null);
  const [selectedCountyOcdid, setSelectedCountyOcdid] = useState(null);
  const [people, setPeople] = useState([]);
  const [dashboardData, setDashboardData] = useState(null);
  const [coverageSummary, setCoverageSummary] = useState({});
  const { localStatus, toReviewCount } = useStateCoverage(selectedState);
  const { reviewStats, activeSession } = useReviewProgress(user, selectedState);
  const {
    selection: searchSelection,
    open: openJurisdiction,
    close: handleModalClose,
  } = useJurisdictionModal();

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

  const handleCountyChange = (event) => {
    setSelectedCountyOcdid(event.detail.jurisdiction_ocdid);
    setSelectedJurisdictionOcdid(null);
  };

  // Clicking a local jurisdiction on the map is the same intent as picking one from
  // search, so it opens the same modal rather than only filling the directory below.
  const handleSelectJurisdictionChange = (event) => {
    const { jurisdiction_ocdid } = event.detail;
    setSelectedJurisdictionOcdid(jurisdiction_ocdid);
    if (jurisdiction_ocdid) openJurisdiction({ jurisdiction_ocdid });
  };

  // A search hit opens the modal rather than filtering the page: the browse flow below
  // stays where it was, and the answer is not somewhere the reader has to hunt for.
  const handleSearchSelect = (event) => openJurisdiction(event.detail);

  return html`
    <div class="home-page">
      <hgroup>
        <h1>Find your local representatives</h1>
        <p>
          Find contact information for local government officials across the
          U.S.
        </p>
      </hgroup>
      <div class="home-page__grid">
        <div class="home-page__select-col">
          <div class="home-page__finder">
            <h3 class="home-page__finder-title">
              Find your representatives
            </h3>

            <civ-jurisdiction-search
              @jurisdiction-select=${handleSearchSelect}
            ></civ-jurisdiction-search>

            <p class="home-page__finder-or">
              <span>or browse by state</span>
            </p>

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
                    ${dashboardData.states[selectedState].civicpatch.localities
                      .known}
                    municipalities <i class="fa-solid fa-arrow-right"></i>
                  </a>
                `
              : ""}
          </div>

          <civ-verify-cta
            .isLoggedIn=${!!user}
            .toReviewCount=${user
              ? (reviewStats?.available_count ?? 0)
              : toReviewCount}
            .state=${selectedState}
            .hasActiveSession=${activeSession != null}
          ></civ-verify-cta>

          ${renderContributionCard({
            isLoggedIn: !!user,
            dailyCounts: reviewStats?.daily_counts ?? [],
            streak: reviewStats?.streak ?? 0,
            currentDate: reviewStats?.current_date ?? null,
            allTimeResolved: reviewStats?.all_time_resolved ?? 0,
            avgSecondsPerReview: reviewStats?.avg_seconds_per_review ?? null,
          })}
        </div>

        <div class="home-page__map-col">
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
        </div>
      </div>

      ${searchSelection
        ? html`<civ-jurisdiction-modal
            .jurisdictionOcdid=${searchSelection.jurisdiction_ocdid}
            .displayName=${searchSelection.display_name || ""}
            .parentNames=${searchSelection.parent_names || []}
            @close-jurisdiction=${handleModalClose}
          ></civ-jurisdiction-modal>`
        : ""}

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
