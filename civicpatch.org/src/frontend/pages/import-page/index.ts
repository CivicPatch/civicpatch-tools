import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { ref } from "lit/directives/ref.js";
import { usePagerRef } from "../../hooks/use-pager-ref.js";
import { formatDateTime } from "../../utils/date-utils.js";
import {
  startImport,
  fetchLatestImport,
  fetchSheetUrl,
  fetchImportHistory,
  fetchImportProgress,
  fetchBatchReview,
  publishBatch,
} from "../../api.js";
import {
  BATCH_FAILED,
  isFinished,
  type BatchReview,
  type ImportPreview,
  type ImportProgress,
  type PublishResult,
} from "./import-types.js";
import { Pagination } from "../../components/pagination/index.js";
import "./import-preview.js";
import "./batch-review.js";
import "../../components/panel/panel.css";
import "./import-page.css";
import { useAuth } from "../../hooks/useAuth.js";
import { SectionNav, manageSection } from "../../components/section-nav/index.js";
import { useSummary } from "../../hooks/useSummary.js";

const POLL_INTERVAL_MS = 2000;
const HISTORY_PER_PAGE = 10;

function progressPanel(batch: ImportProgress | null) {
  // Null for the moment between starting and the first poll returning.
  const total = batch?.items_total;
  return html`
    <section class="panel import-panel import-progress">
      <h3 class="import-section__title">Importing…</h3>
      <p class="import-progress__count">
        ${batch ? batch.items_done : 0}${total == null ? "" : ` of ${total}`}
        localities
      </p>
      <p class="import-hint">
        ${batch
          ? `Started ${new Date(batch.started_at).toLocaleTimeString()}. `
          : ""}Each
        locality becomes an ordinary review card. Nothing is published yet.
      </p>
    </section>
  `;
}

function resultsPanel(results: PublishResult[]) {
  if (!results.length) return null;
  const failed = results.filter((result) => !result.published);
  const published = results.length - failed.length;
  return html`
    <section class="import-results">
      <p>
        Published ${published} of ${results.length}, in one open-data commit.
      </p>
      ${failed.map(
        (result) => html`
          <p class="import-results__failure">
            ${result.jurisdiction_ocdid}: ${result.error}
          </p>
        `,
      )}
    </section>
  `;
}

function batchHeader(batch: ImportProgress) {
  return html`
    <header class="import-batch__header">
      <span>${formatDateTime(batch.started_at)}</span>
      <span>${batch.status}</span>
      ${batch.status === BATCH_FAILED && batch.error
        ? html`<span class="import-batch__error">${batch.error}</span>`
        : null}
    </header>
  `;
}

function ImportPage() {
  const { permissions } = useAuth();
  // Global, not scoped to any page's own state — the sidebar badge is a constant
  // "how much is waiting overall" figure, the same wherever it appears.
  const globalSummary = useSummary(true, "");
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  // The batch being tracked, kept apart from its progress: starting an import sets this, and
  // that is what makes the poll below begin. Folding them together is why a fresh import used
  // to sit on "Importing…" until a reload.
  const [batchId, setBatchId] = useState<string | null>(null);
  const [batch, setBatch] = useState<ImportProgress | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sheetUrl, setSheetUrl] = useState<string | null>(null);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyTotalPages, setHistoryTotalPages] = useState(1);
  const [history, setHistory] = useState<ImportProgress[]>([]);
  const { listRef: historyRef, scrollToTop } = usePagerRef<HTMLElement>();
  // Keyed by batch id: every batch on the current page gets its own review, its own publish
  // results, and its own busy flag, rather than one page-wide set that only ever tracked the
  // single most recently started batch.
  const [reviews, setReviews] = useState<Record<string, BatchReview>>({});
  const [resultsByBatch, setResultsByBatch] = useState<
    Record<string, PublishResult[]>
  >({});
  const [publishingBatchId, setPublishingBatchId] = useState<string | null>(null);

  // Refreshed whenever a batch changes or the page turns, so finishing an import updates the
  // list in place rather than leaving it stale until a reload.
  useEffect(() => {
    fetchImportHistory(historyPage, HISTORY_PER_PAGE)
      .then(({ data, total_pages }) => {
        setHistory(data);
        setHistoryTotalPages(total_pages || 1);
      })
      .catch(() => {
        // A missing history is not worth an error banner over the import itself.
      });
  }, [historyPage, batch?.batch_id, batch?.status]);

  // One review per finished batch on the current page. A batch still running has none yet —
  // the progress panel above already covers that one.
  useEffect(() => {
    const finished = history.filter((b) => isFinished(b.status));
    if (!finished.length) return;
    let stopped = false;
    Promise.all(
      finished.map((b) =>
        fetchBatchReview(b.batch_id).then((r) => [b.batch_id, r.data] as const),
      ),
    )
      .then((pairs) => {
        if (stopped) return;
        setReviews(Object.fromEntries(pairs));
      })
      .catch(() => {
        // A missing review reads as "nothing to show" for that batch, not a page-wide error.
      });
    return () => {
      stopped = true;
    };
  }, [history]);

  useEffect(() => {
    fetchSheetUrl()
      .then(({ data }) => setSheetUrl(data.url))
      .catch(() => {
        // A missing link is not worth an error banner; the button still works.
      });
  }, []);

  // Which batch to show comes from the server, not from this browser: one spreadsheet means one
  // import, so whoever opens the page should find whatever is under way.
  useEffect(() => {
    let stopped = false;
    fetchLatestImport()
      .then(({ data }) => {
        if (stopped || !data) return;
        setBatch(data);
        setBatchId(data.batch_id);
      })
      .catch((e) => {
        if (!stopped) setError(String(e));
      });
    return () => {
      stopped = true;
    };
  }, []);

  // Poll whichever batch is being tracked until it finishes. Its review arrives through the
  // history-and-reviews effects above once it shows up there — not fetched here directly.
  useEffect(() => {
    if (!batchId) return;
    let stopped = false;
    let timer = 0;

    const poll = async () => {
      if (stopped) return;
      try {
        const { data } = await fetchImportProgress(batchId);
        if (stopped) return;
        setBatch(data);
        if (!isFinished(data.status)) {
          timer = window.setTimeout(poll, POLL_INTERVAL_MS);
          return;
        }
        if (data.status === BATCH_FAILED && data.error) setError(data.error);
      } catch (e) {
        if (!stopped) setError(String(e));
      }
    };

    poll();
    return () => {
      stopped = true;
      window.clearTimeout(timer);
    };
  }, [batchId]);

  // Tracked and not known-finished. Keyed off the id, not the progress, so the moment an
  // import starts the page shows it rather than flashing back to the Check panel.
  const running =
    batchId !== null && (batch === null || !isFinished(batch.status));

  const handleStart = async () => {
    setBusy(true);
    setError(null);
    try {
      const { data } = await startImport();
      setPreview(data.preview);
      // Setting the id is what starts the poll — do not also fetch progress here.
      setBatchId(data.batch_id);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const handlePublish = (targetBatchId: string) => async (e: CustomEvent) => {
    setPublishingBatchId(targetBatchId);
    setError(null);
    try {
      const { data } = await publishBatch(
        targetBatchId,
        e.detail.jurisdiction_ocdids,
      );
      setResultsByBatch((prev) => ({ ...prev, [targetBatchId]: data }));
      // Re-read rather than patching locally: publishing is what decides the review status,
      // and a locality that refused must still show as pending.
      const reviewBody = await fetchBatchReview(targetBatchId);
      setReviews((prev) => ({ ...prev, [targetBatchId]: reviewBody.data }));
    } catch (err) {
      setError(String(err));
    } finally {
      setPublishingBatchId(null);
    }
  };

  // Built once so Next/Previous re-orients to the top of the history section either way —
  // clicking the bottom pager most often leaves the reader below what just changed above them.
  const historyPager = Pagination({
    page: historyPage,
    totalPages: historyTotalPages,
    onPrevious: () => {
      setHistoryPage(Math.max(historyPage - 1, 1));
      scrollToTop();
    },
    onNext: () => {
      setHistoryPage(Math.min(historyPage + 1, historyTotalPages));
      scrollToTop();
    },
  });

  return html`
    <main class="import-page page-content">
      <div class="page-focal">
        <h1 class="page-focal__title">Sheet import</h1>
      </div>
      <div class="sectioned">
      ${SectionNav("manage", manageSection(permissions, globalSummary?.open_prs), "/imports")}
      <div class="secbody">
      <p class="import-hint">
        The curated roster sheet, read as a scrape. Importing raises a review
        card per locality. Publishing stays your decision.
      </p>

      ${error ? html`<p class="import-error">${error}</p>` : null}

      ${running
        ? progressPanel(batch)
        : html`
            <section class="panel import-panel">
              <h2 class="import-panel__title">Import from the sheet</h2>
              ${sheetUrl
                ? html`<p class="import-hint">
                    <a href=${sheetUrl} target="_blank" rel="noreferrer"
                      >Open the sheet</a
                    >
                  </p>`
                : null}
              <button
                type="button"
                class="import-action"
                ?disabled=${busy}
                @click=${handleStart}
              >
                ${busy ? "Importing…" : "Import"}
              </button>
            </section>
          `}

      ${preview
        ? html`<section class="panel import-panel">
            <import-preview .preview=${preview}></import-preview>
          </section>`
        : null}

      ${history.length
        ? html`
            <div ${ref(historyRef)}>
            <h2 class="import-panel__title">Past imports</h2>
            ${historyPager}
            ${history.map(
              (b) => html`
                <section class="panel import-panel">
                  ${batchHeader(b)}
                  ${resultsPanel(resultsByBatch[b.batch_id] ?? [])}
                  ${reviews[b.batch_id]
                    ? html`<batch-review
                        .review=${reviews[b.batch_id]}
                        .importedAt=${b.started_at}
                        .busy=${publishingBatchId === b.batch_id}
                        @publish-selection=${handlePublish(b.batch_id)}
                      ></batch-review>`
                    : null}
                </section>
              `,
            )}
            ${historyPager}
            </div>
          `
        : null}
      </div>
      </div>
    </main>
  `;
}

customElements.define(
  "import-page",
  component(ImportPage, {
    useShadowDOM: false,
  }),
);
export default ImportPage;
