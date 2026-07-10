import "./search-jurisdictions.css";
import { component, useState, useEffect } from "haunted";
import { html } from "lit-html";
import {
  fetchPeople,
  fetchDashboard,
  fetchMapsCoverage,
  fetchLocalStatus,
  fetchStateCoverageSummary,
  fetchReviewStats,
  fetchActiveReviewSession,
} from "../../api.js";
import {
  useLocalStorage,
  PERSIST_FOREVER,
} from "../../hooks/use-local-storage.js";
import { useAuth } from "../../hooks/useAuth.js";
import "../../components/badge/badge.js";
import "../../components/leaderboard/index.js";
import "../../components/progress-dashboard/locality-gaps.js";
import "../../components/people-directory/people-directory.ts";
import "../../components/map/browse-map.ts";
import "../../components/verify-cta/verify-cta.ts";
import { renderContributionCard } from "../contribution-card/contribution-card.ts";
import { renderFreshnessWidget } from "../../components/progress-dashboard/freshness-widget.ts";
import { getNeedsReviewCount } from "../../utils/coverage-utils.js";

function SearchJurisdictions() {
  const { user, permissions } = useAuth();
  const [defaultState] = useLocalStorage("app:default-state", "", {
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
  const [localStatus, setLocalStatus] = useState({});
  const [toReviewCount, setToReviewCount] = useState(0);
  const [reviewStats, setReviewStats] = useState(null);
  const [activeSession, setActiveSession] = useState(null);

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

  useEffect(() => {
    if (!selectedState) {
      setLocalStatus({});
      return;
    }
    fetchLocalStatus(selectedState)
      .then((d) => setLocalStatus(d.data ?? {}))
      .catch(() => {});
  }, [selectedState]);

  useEffect(() => {
    if (!selectedState) {
      setToReviewCount(0);
      return;
    }
    fetchStateCoverageSummary(selectedState)
      .then((d) => setToReviewCount(getNeedsReviewCount(d.data)))
      .catch(() => {});
  }, [selectedState]);

  useEffect(() => {
    // review-sessions/stats requires auth (AUTHENTICATED route) — skip the call
    // entirely for anonymous visitors, the common case (see plan §13).
    if (!user || !selectedState) {
      setReviewStats(null);
      return;
    }
    fetchReviewStats(selectedState)
      .then((d) => setReviewStats(d.data ?? null))
      .catch(() => setReviewStats(null));
  }, [user, selectedState]);

  useEffect(() => {
    // review-sessions/active requires auth too — same anonymous-visitor skip as
    // reviewStats above.
    if (!user || !selectedState) {
      setActiveSession(null);
      return;
    }
    fetchActiveReviewSession(selectedState)
      .then((d) => setActiveSession(d.data ?? null))
      .catch(() => setActiveSession(null));
  }, [user, selectedState]);

  const handleStateChange = (event) => {
    setSelectedState((event.detail.state || "").toLowerCase());
    setSelectedCountyOcdid(null);
    setSelectedJurisdictionOcdid(null);
  };

  const handleCountyChange = (event) => {
    setSelectedCountyOcdid(event.detail.jurisdiction_ocdid);
    setSelectedJurisdictionOcdid(null);
  };

  const handleSelectJurisdictionChange = (event) => {
    const { jurisdiction_ocdid } = event.detail;
    setSelectedJurisdictionOcdid(jurisdiction_ocdid);
  };

  return html`
    <div class="search-page">
      <hgroup>
        <h1>Find your local representatives</h1>
        <p>
          Find contact information for local government officials across the
          U.S.
        </p>
      </hgroup>
      <div class="page-grid">
        <div class="select-col">
          <div class="find-representatives">
            <h3 class="find-representatives__title">States</h3>
            <civ-select-state
              .selected=${selectedState}
              @state-change=${handleStateChange}
            ></civ-select-state>

            ${selectedState && dashboardData?.states?.[selectedState]
              ? html`
                  <a
                    class="browse-municipalities-link"
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
            .toReviewCount=${user ? (reviewStats?.available_count ?? 0) : toReviewCount}
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

        <div class="map-col">
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

      <div class="below-grid">
        <civ-people-directory
          .local=${people}
          .jurisdictionSelected=${!!selectedJurisdictionOcdid}
        ></civ-people-directory>
      </div>
    </div>
  `;
}

customElements.define(
  "civ-search-jurisdictions",
  component(SearchJurisdictions, {
    useShadowDOM: false,
    observedAttributes: [],
  }),
);
