import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
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
import "../../components/civ-tab-bar/civ-tab-bar.js";
import "./import-history.js";
import "./import-preview.js";
import "./batch-review.js";
import "./import-page.css";

const POLL_INTERVAL_MS = 2000;
const TABS = [{ label: "Import" }, { label: "History" }];
const IMPORT_TAB = 0;
const HISTORY_TAB = 1;

function progressPanel(batch: ImportProgress | null) {
  // Null for the moment between starting and the first poll returning.
  const total = batch?.items_total;
  return html`
    <section class="import-panel import-progress">
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

function ImportPage() {
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  // The batch being tracked, kept apart from its progress: starting an import sets this, and
  // that is what makes the poll below begin. Folding them together is why a fresh import used
  // to sit on "Importing…" until a reload.
  const [batchId, setBatchId] = useState<string | null>(null);
  const [batch, setBatch] = useState<ImportProgress | null>(null);
  const [review, setReview] = useState<BatchReview | null>(null);
  const [results, setResults] = useState<PublishResult[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sheetUrl, setSheetUrl] = useState<string | null>(null);
  const [tab, setTab] = useState(IMPORT_TAB);
  const [history, setHistory] = useState<ImportProgress[]>([]);

  // Refreshed whenever a batch changes, so finishing an import updates the list behind the tab
  // rather than leaving it stale until a reload.
  useEffect(() => {
    fetchImportHistory()
      .then(({ data }) => setHistory(data))
      .catch(() => {
        // A missing history is not worth an error banner over the import itself.
      });
  }, [batch?.batch_id, batch?.status]);

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

  // Poll whichever batch is being tracked until it finishes, then read its review.
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
        const reviewBody = await fetchBatchReview(batchId);
        if (stopped) return;
        setReview(reviewBody.data);
        // Finished, so it is a past import now: the review lives beside the run that produced
        // it rather than under the button that starts the next one.
        setTab(HISTORY_TAB);
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
    setReview(null);
    setResults([]);
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

  // Opening a past batch swaps which one the page is following: the poll effect keys on the
  // id, so setting it is enough to load that batch's review instead of the latest one's.
  const handleOpenBatch = (e: CustomEvent) => {
    setReview(null);
    setResults([]);
    setError(null);
    setBatchId(e.detail.batch_id);
  };

  const handlePublish = async (e: CustomEvent) => {
    if (!batch) return;
    setBusy(true);
    setError(null);
    try {
      const { data } = await publishBatch(
        batch.batch_id,
        e.detail.jurisdiction_ocdids,
      );
      setResults(data);
      // Re-read rather than patching locally: publishing is what decides the review status,
      // and a locality that refused must still show as pending.
      const reviewBody = await fetchBatchReview(batch.batch_id);
      setReview(reviewBody.data);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  };

  return html`
    <main class="container import-page">
      <header class="import-page__header">
        <h1>Sheet import</h1>
        <p class="import-hint">
          The curated roster sheet, read as a scrape. Importing raises a review
          card per locality. Publishing stays your decision.
        </p>
      </header>

      <civ-tab-bar
        .tabs=${TABS}
        .selectedIndex=${tab}
        .onTabClick=${(index: number) => setTab(index)}
      ></civ-tab-bar>

      ${error ? html`<p class="import-error">${error}</p>` : null}
      ${resultsPanel(results)}
      ${tab === HISTORY_TAB
        ? html`<section class="import-panel">
            <h2 class="import-panel__title">Past imports</h2>
            <import-history
              .batches=${history}
              .currentBatchId=${batchId}
              @open-batch=${handleOpenBatch}
            ></import-history>
          </section>`
        : html`${running
            ? progressPanel(batch)
            : html`
                <section class="import-panel">
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
              `}`}
      ${preview
        ? html`<section class="import-panel">
            <import-preview .preview=${preview}></import-preview>
          </section>`
        : null}
      ${tab === HISTORY_TAB && review
        ? html`<section class="import-panel">
            <batch-review
              .review=${review}
              .busy=${busy}
              @publish-selection=${handlePublish}
            ></batch-review>
          </section>`
        : null}
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
