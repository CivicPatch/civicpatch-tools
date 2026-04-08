import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { useAuth } from "../../hooks/useAuth.js";
import { useLocalStorage, PERSIST_FOREVER } from "../../hooks/use-local-storage.js";
import { useSummary } from "../../hooks/useSummary.js";
import {
  fetchJobsWithErrors,
  fetchJobEvents,
  fetchDuplicatePrJurisdictionJobs,
  fetchPullRequests,
  closeStaleDuplicatePrs,
  resolveJob,
  resumeJob,
  saveAndMerge,
  closePullRequest,
} from "../../api.js";
import { PULL_REQUEST_STATUS } from "../../components/pull-request-card/pull-request-status.js";
import "../../components/pull-request-card/index.js";
import "../queue-page/error-card/index.js";
import { Pagination } from "../../components/pagination/index.js";
import "./issues-page.css";

const DEFAULT_EVENTS_PER_PAGE = 20;
const EVENTS_PER_PAGE_OPTIONS = [10, 20, 50, 100];

const KNOWN_EVENT_TYPES = [
  { value: "unrecognized_role", label: "Unrecognized role" },
  { value: "dead_url", label: "Dead URL" },
  { value: "excluded_person", label: "Excluded person" },
];

function getEventsPageFromUrl() {
  const val = parseInt(new URLSearchParams(window.location.search).get("events_page"), 10);
  return isNaN(val) || val < 1 ? 1 : val;
}

function getEventsPerPageFromUrl() {
  const val = parseInt(new URLSearchParams(window.location.search).get("events_per_page"), 10);
  return EVENTS_PER_PAGE_OPTIONS.includes(val) ? val : DEFAULT_EVENTS_PER_PAGE;
}

function getEventsTagsFromUrl() {
  const val = new URLSearchParams(window.location.search).get("events_tags");
  return val ? val.split(",").filter(Boolean) : [];
}

function getEventsSortDescFromUrl() {
  return new URLSearchParams(window.location.search).get("events_sort") !== "asc";
}

function setEventsPageInUrl(page) {
  const params = new URLSearchParams(window.location.search);
  params.set("events_page", page);
  window.history.pushState({}, "", `${window.location.pathname}?${params}`);
}

function setEventsParamsInUrl(page, perPage, tags, sortDesc) {
  const params = new URLSearchParams(window.location.search);
  params.set("events_page", page);
  params.set("events_per_page", perPage);
  if (tags && tags.length) params.set("events_tags", tags.join(","));
  else params.delete("events_tags");
  params.set("events_sort", sortDesc ? "desc" : "asc");
  window.history.pushState({}, "", `${window.location.pathname}?${params}`);
}


function getEventDetail(eventType, data) {
  if (!data) return "";
  if (eventType === "unrecognized_role") return `${data.role} — ${data.person_name}`;
  if (eventType === "dead_url") return data.url;
  if (eventType === "excluded_person") return data.name;
  return JSON.stringify(data);
}

function formatEventType(eventType) {
  return KNOWN_EVENT_TYPES.find((t) => t.value === eventType)?.label ?? eventType;
}

function formatDate(isoString) {
  if (!isoString) return "";
  return new Date(isoString).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

function IssuesPage() {
  const { permissions } = useAuth();
  const summary = useSummary(true);

  // Errors section
  const [errorJobs, setErrorJobs] = useState([]);
  const [errorsLoading, setErrorsLoading] = useState(false);

  // Events section
  const [events, setEvents] = useState([]);
  const [eventsTotal, setEventsTotal] = useState(0);
  const [eventsPage, setEventsPage] = useState(getEventsPageFromUrl());
  const [eventsPerPage, setEventsPerPage] = useState(getEventsPerPageFromUrl());
  const [eventsTagFilter, setEventsTagFilter] = useState(getEventsTagsFromUrl());
  const [eventsSortDesc, setEventsSortDesc] = useState(getEventsSortDescFromUrl());
  const [eventsLoading, setEventsLoading] = useState(false);
  const [eventsPageLoading, setEventsPageLoading] = useState(false);

  // Duplicates section
  const [duplicateJurisdictions, setDuplicateJurisdictions] = useState([]);
  const [duplicateJurisdictionPRs, setDuplicateJurisdictionPRs] = useState({});
  const [openJurisdictions, setOpenJurisdictions] = useState({});
  const [closingStale, setClosingStale] = useState(false);
  const [prState, setPrState] = useState({});

  const [openSections, setOpenSections] = useLocalStorage(
    "issues-page:open-sections",
    { errors: true, events: true, duplicates: true },
    { ttl: PERSIST_FOREVER },
  );
  const toggleSection = (key) => setOpenSections({ ...openSections, [key]: !openSections[key] });

  // Sync URL → state on browser back/forward
  useEffect(() => {
    const onPopState = () => {
      setEventsPage(getEventsPageFromUrl());
      setEventsPerPage(getEventsPerPageFromUrl());
      setEventsTagFilter(getEventsTagsFromUrl());
      setEventsSortDesc(getEventsSortDescFromUrl());
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  // Errors — lazy, only when section is open
  useEffect(() => {
    if (!openSections.errors) return;
    setErrorsLoading(true);
    fetchJobsWithErrors()
      .then((r) => setErrorJobs(r.data || []))
      .catch(console.error)
      .finally(() => setErrorsLoading(false));
  }, [openSections.errors]);

  // Events — lazy, refetch on any filter/page/sort change
  useEffect(() => {
    if (!openSections.events) return;
    setEventsLoading(true);
    fetchJobEvents(eventsTagFilter, eventsPage, eventsPerPage, eventsSortDesc ? "desc" : "asc")
      .then((r) => { setEvents(r.data || []); setEventsTotal(r.total || 0); })
      .catch(console.error)
      .finally(() => { setEventsLoading(false); setEventsPageLoading(false); });
  }, [openSections.events, eventsPage, eventsPerPage, eventsTagFilter, eventsSortDesc]);

  // Duplicates — lazy, only when section is open
  useEffect(() => {
    if (!openSections.duplicates) return;
    fetchDuplicatePrJurisdictionJobs()
      .then((r) => setDuplicateJurisdictions(r.data || []))
      .catch(console.error);
  }, [openSections.duplicates]);

  const handleResolveError = async (event) => {
    const { job } = event.detail;
    try {
      await resolveJob(job.request_id);
      setErrorJobs(errorJobs.filter((j) => j.request_id !== job.request_id));
    } catch (err) {
      console.error("Failed to resolve job:", err);
    }
  };

  const handleResumeJob = async (event) => {
    const { job } = event.detail;
    try {
      await resumeJob(job.request_id);
      setErrorJobs(errorJobs.filter((j) => j.request_id !== job.request_id));
    } catch (err) {
      console.error("Failed to resume job:", err);
    }
  };

  const handleToggleTag = (tag) => {
    const next = eventsTagFilter.includes(tag)
      ? eventsTagFilter.filter((t) => t !== tag)
      : [...eventsTagFilter, tag];
    setEventsTagFilter(next);
    setEventsPage(1);
    setEventsParamsInUrl(1, eventsPerPage, next, eventsSortDesc);
  };

  const handleToggleSort = () => {
    const next = !eventsSortDesc;
    setEventsSortDesc(next);
    setEventsPage(1);
    setEventsParamsInUrl(1, eventsPerPage, eventsTagFilter, next);
  };

  const goToEventsPage = (newPage) => {
    setEventsPageLoading(true);
    setEventsPageInUrl(newPage);
    setEventsPage(newPage);
  };

  const handleEventsPerPageChange = (e) => {
    const newPerPage = parseInt(e.target.value, 10);
    setEventsPerPage(newPerPage);
    setEventsPage(1);
    setEventsParamsInUrl(1, newPerPage, eventsTagFilter, eventsSortDesc);
  };

  const loadJurisdictionPRs = async (ocdid) => {
    setOpenJurisdictions((prev) => ({ ...prev, [ocdid]: !prev[ocdid] }));
    if (!duplicateJurisdictionPRs[ocdid]) {
      const result = await fetchPullRequests(ocdid);
      setDuplicateJurisdictionPRs((prev) => ({ ...prev, [ocdid]: result.data || [] }));
    }
  };

  const handleCloseStaleDuplicates = async () => {
    setClosingStale(true);
    try {
      await closeStaleDuplicatePrs();
      const result = await fetchDuplicatePrJurisdictionJobs();
      setDuplicateJurisdictions(result.data || []);
      setDuplicateJurisdictionPRs({});
      setOpenJurisdictions({});
    } finally {
      setClosingStale(false);
    }
  };

  const handleDuplicateMerge = async (event) => {
    const { pullRequestNumber, request_id, jurisdiction_ocdid } = event.detail;
    try {
      setPrState({ ...prState, [pullRequestNumber]: { status: PULL_REQUEST_STATUS.LOADING_MERGE } });
      await saveAndMerge(pullRequestNumber, request_id, jurisdiction_ocdid, null);
      setPrState({ ...prState, [pullRequestNumber]: { status: PULL_REQUEST_STATUS.MERGED } });
    } catch (err) {
      setPrState({ ...prState, [pullRequestNumber]: { status: PULL_REQUEST_STATUS.ERROR, error: err } });
    }
  };

  const handleDuplicateClose = async (event) => {
    const { pullRequestNumber, request_id } = event.detail;
    try {
      setPrState({ ...prState, [pullRequestNumber]: { status: PULL_REQUEST_STATUS.LOADING_CLOSE } });
      await closePullRequest(request_id, pullRequestNumber);
      setPrState({ ...prState, [pullRequestNumber]: { status: PULL_REQUEST_STATUS.CLOSED } });
    } catch (err) {
      setPrState({ ...prState, [pullRequestNumber]: { status: PULL_REQUEST_STATUS.ERROR, error: err } });
    }
  };

  const eventsTotalPages = Math.ceil(eventsTotal / eventsPerPage);

  // --- Render helpers ---

  const eventsPaginationControls = !eventsPageLoading ? Pagination({
    page: eventsPage,
    totalPages: eventsTotalPages,
    onPrevious: () => goToEventsPage(eventsPage - 1),
    onNext: () => goToEventsPage(eventsPage + 1),
    onGoToPage: goToEventsPage,
    hrefForPage: (n) => `?events_page=${n}`,
  }) : null;

  const tagChips = KNOWN_EVENT_TYPES.map(({ value, label }) => {
    const active = eventsTagFilter.includes(value);
    return html`
      <button
        class="issues-page__event-tag${active ? " issues-page__event-tag--active" : ""}"
        @click=${() => handleToggleTag(value)}
      >${label}${active ? html` <span class="issues-page__event-tag-x">×</span>` : ""}</button>
    `;
  });

  const eventsSection = html`
    <section class="issues-page__section">
      <div class="issues-page__section-header" @click=${() => toggleSection("events")}>
        <h2 class="issues-page__section-title issues-page__section-title--info">Events <span class="issues-page__section-count">${eventsTotal || summary?.events_total || ""}</span></h2>
        <i class="fa-solid fa-chevron-down btn-icon${openSections.events ? " btn-icon--rotated" : ""}"></i>
      </div>
      ${openSections.events ? html`
        <div class="issues-page__events-filters">
          <div class="issues-page__event-tags">${tagChips}</div>
          <button
            class="btn btn-sm issues-page__sort-btn"
            @click=${handleToggleSort}
          >${eventsSortDesc ? "Newest ↓" : "Oldest ↑"}</button>
        </div>
        ${eventsLoading ? html`<div>Loading…</div>` : html`
          <table class="issues-page__events-table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Detail</th>
                <th>Jurisdiction</th>
                <th>Date</th>
              </tr>
            </thead>
            <tbody>
              ${events.length === 0
                ? html`<tr><td colspan="4">No events found.</td></tr>`
                : events.map((ev) => html`
                  <tr>
                    <td><span class="issues-page__event-type-chip issues-page__event-type-chip--${ev.event_type.replace(/_/g, "-")}">${formatEventType(ev.event_type)}</span></td>
                    <td class="issues-page__event-detail">${getEventDetail(ev.event_type, ev.data)}</td>
                    <td>
                      ${ev.jurisdiction_ocdid
                        ? html`<a href="/jurisdictions?jurisdiction_ocdid=${ev.jurisdiction_ocdid}" target="_blank">${ev.jurisdiction_name || ev.jurisdiction_ocdid}</a>`
                        : "—"}
                    </td>
                    <td class="issues-page__event-date">${formatDate(ev.created_at)}</td>
                  </tr>
                `)
              }
            </tbody>
          </table>
          <div class="issues-page__top-controls">
            <div class="issues-page__pagination">
              ${eventsPaginationControls}
            </div>
            <label class="issues-page__per-page">
              Per page
              <select @change=${handleEventsPerPageChange}>
                ${EVENTS_PER_PAGE_OPTIONS.map(
                  (n) => html`<option value=${n} ?selected=${n === eventsPerPage}>${n}</option>`
                )}
              </select>
            </label>
          </div>
        `}
      ` : null}
    </section>
  `;

  const errorsCount = openSections.errors ? errorJobs.length : (summary?.pipeline_errors ?? "");
  const errorsSection = html`
    <section class="issues-page__section">
      ${errorsCount === 0 && !errorsLoading ? html`
        <h2 class="issues-page__section-title issues-page__section-title--error">Pipeline errors <span class="issues-page__section-count">0</span></h2>
      ` : html`
        <div class="issues-page__section-header" @click=${() => toggleSection("errors")}>
          <h2 class="issues-page__section-title issues-page__section-title--error">Pipeline errors <span class="issues-page__section-count">${errorsCount}</span></h2>
          <i class="fa-solid fa-chevron-down btn-icon${openSections.errors ? " btn-icon--rotated" : ""}"></i>
        </div>
        ${openSections.errors ? html`
          ${errorsLoading
            ? html`<div>Loading…</div>`
            : html`<div style="display:flex;gap:2rem;flex-direction:column;">${errorJobs.map((job) => html`<error-card .job=${job} @resolve-error=${handleResolveError} @resume-job=${handleResumeJob}></error-card>`)}</div>`
          }
        ` : null}
      `}
    </section>
  `;

  const duplicatePrList = duplicateJurisdictions.map((ocdid) => {
    const isOpen = openJurisdictions[ocdid];
    return html`
      <div class="issues-page__duplicate-item">
        <button
          class="issues-page__duplicate-item-header${isOpen ? " issues-page__duplicate-item-header--open" : ""}"
          @click=${() => loadJurisdictionPRs(ocdid)}
        >
          <span>${ocdid}</span>
          <i class="fa-solid fa-chevron-down btn-icon${isOpen ? " btn-icon--rotated" : ""}"></i>
        </button>
        ${isOpen ? html`
          <div class="issues-page__duplicate-item-body">
            ${(duplicateJurisdictionPRs[ocdid] || []).map((pr) => {
              const pullRequestNumber = pr.pr.number;
              return html`
                <pr-card
                  @onMerge=${handleDuplicateMerge}
                  @onClose=${handleDuplicateClose}
                  .entry=${pr}
                  .state=${prState[pullRequestNumber]}
                ></pr-card>
              `;
            })}
          </div>
        ` : null}
      </div>
    `;
  });

  const duplicatesCount = openSections.duplicates ? duplicateJurisdictions.length : (summary?.duplicate_jurisdictions ?? "");
  const duplicatesSection = html`
    <section class="issues-page__section">
      ${duplicatesCount === 0 ? html`
        <h2 class="issues-page__section-title issues-page__section-title--warning">Duplicate jurisdictions <span class="issues-page__section-count">0</span></h2>
      ` : html`
        <div class="issues-page__section-header" @click=${() => toggleSection("duplicates")}>
          <h2 class="issues-page__section-title issues-page__section-title--warning">Duplicate jurisdictions <span class="issues-page__section-count">${duplicatesCount}</span></h2>
          <i class="fa-solid fa-chevron-down btn-icon${openSections.duplicates ? " btn-icon--rotated" : ""}"></i>
        </div>
        ${openSections.duplicates ? html`
          <button
            class="btn btn-sm destructive"
            @click=${handleCloseStaleDuplicates}
            ?disabled=${closingStale}
          >${closingStale ? "Closing…" : "Close stale"}</button>
          <div class="issues-page__duplicate-list">${duplicatePrList}</div>
        ` : null}
      `}
    </section>
  `;

  return html`
    <main class="issues-page page-content">
      ${errorsSection}
      ${eventsSection}
      ${duplicatesSection}
    </main>
  `;
}

customElements.define(
  "issues-page",
  component(IssuesPage, { useShadowDOM: false }),
);
export default IssuesPage;
