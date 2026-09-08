import "./pipeline-runs-page.css";
import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { useAuth } from "../../hooks/useAuth.js";
import { useLocalStorage, PERSIST_FOREVER } from "../../hooks/use-local-storage.js";
import { STORAGE_KEYS } from "../../utils/storage-keys.js";
import { fetchActivePipelineRuns } from "../../api.js";
import "./active-runs/index.js";

const PER_PAGE_CHOICES = [10, 25, 50];

function getIntParam(key: string, fallback: number, allowed: number[] | null = null): number {
  const val = parseInt(new URLSearchParams(window.location.search).get(key) ?? "", 10);
  if (isNaN(val) || val < 1) return fallback;
  if (allowed && !allowed.includes(val)) return fallback;
  return val;
}

function getStateFromUrl(): string {
  const val = new URLSearchParams(window.location.search).get("state");
  return val ? val.toLowerCase() : "";
}

function setParamsInUrl(page: number, perPage: number): void {
  const params = new URLSearchParams(window.location.search);
  params.set("page", String(page));
  params.set("per_page", String(perPage));
  window.history.pushState({}, "", `${window.location.pathname}?${params}`);
}

function InFlightPage() {
  const { permissions } = useAuth();
  const [defaultState] = useLocalStorage(STORAGE_KEYS.DEFAULT_STATE, "", { ttl: PERSIST_FOREVER });
  const stateCode = (getStateFromUrl() || defaultState || "").toLowerCase();
  const [runs, setRuns] = useState<any[]>([]);
  const [page, setPage] = useState(getIntParam("page", 1));
  const [perPage, setPerPage] = useState(getIntParam("per_page", 25, PER_PAGE_CHOICES));
  const [totalPages, setTotalPages] = useState(1);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const onPopState = () => {
      setPage(getIntParam("page", 1));
      setPerPage(getIntParam("per_page", 25, PER_PAGE_CHOICES));
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  useEffect(() => {
    fetchActivePipelineRuns(stateCode || undefined, page, perPage)
      .then((result: any) => {
        setRuns(result.data || []);
        setTotalPages(result.total_pages || 1);
      })
      .catch(() => setRuns([]))
      .finally(() => setLoaded(true));
  }, [stateCode, page, perPage]);

  const handlePerPageChange = (e: Event) => {
    const n = parseInt((e.target as HTMLSelectElement).value, 10);
    setParamsInUrl(1, n);
    setPerPage(n);
    setPage(1);
  };

  const running = runs.filter((r) => r.status === "RUNNING").length;

  return html`
    <main class="pipeline-runs page-content">
      <div class="page-focal">
        <h1 class="page-focal__title">Pipeline runs</h1>
        ${runs.length
          ? html`<div class="page-focal__end pipeline-runs__facts">
              <span class="pipeline-runs__fact"><b>${running}</b>running</span>
              <span class="pipeline-runs__fact"><b>${runs.length - running}</b>queued</span>
            </div>`
          : null}
      </div>

      ${loaded && runs.length === 0
        ? html`<p class="pipeline-runs__empty">No runs in progress.</p>`
        : html`
            <pipeline-runs-list
              .jobs=${runs}
              .page=${page}
              .totalPages=${totalPages}
              .perPage=${perPage}
              .onPageChange=${(p: number) => { setParamsInUrl(p, perPage); setPage(p); }}
              .onPerPageChange=${handlePerPageChange}
              .canCancel=${permissions.can_cancel_pipeline_run}
              .onCancel=${(pipelineRunId: string) =>
                setRuns((prev) => prev.filter((j) => j.pipeline_run_id !== pipelineRunId))}
            ></pipeline-runs-list>`}
    </main>
  `;
}

customElements.define("pipeline-runs-page", component(InFlightPage, { useShadowDOM: false }));
