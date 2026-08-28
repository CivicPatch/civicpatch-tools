import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import {
  previewImport,
  startImport,
  fetchLatestImport,
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
import "./import-preview.js";
import "./batch-review.js";
import "./import-page.css";

const POLL_INTERVAL_MS = 2000;

function progressPanel(batch: ImportProgress) {
  const total = batch.items_total;
  return html`
    <section class="import-progress">
      <h3 class="import-towns__title">Importing…</h3>
      <p class="import-progress__count">
        ${batch.items_done}${total == null ? "" : ` of ${total}`} towns
      </p>
      <p class="import-towns__hint">
        Started ${new Date(batch.started_at).toLocaleTimeString()}. Each town
        becomes an ordinary review card — nothing is published yet.
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
  const [batch, setBatch] = useState<ImportProgress | null>(null);
  const [review, setReview] = useState<BatchReview | null>(null);
  const [results, setResults] = useState<PublishResult[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // The batch comes from the server, not from this browser: one spreadsheet means one import,
  // so whoever opens the page should find whatever is under way.
  useEffect(() => {
    let stopped = false;
    let timer = 0;

    const poll = async (batchId: string | null) => {
      if (stopped) return;
      try {
        const { data } = batchId
          ? await fetchImportProgress(batchId)
          : await fetchLatestImport();
        if (stopped) return;
        setBatch(data);
        if (!data) return;
        if (!isFinished(data.status)) {
          timer = window.setTimeout(() => poll(data.batch_id), POLL_INTERVAL_MS);
          return;
        }
        if (data.status === BATCH_FAILED && data.error) setError(data.error);
        const reviewBody = await fetchBatchReview(data.batch_id);
        if (!stopped) setReview(reviewBody.data);
      } catch (e) {
        if (!stopped) setError(String(e));
      }
    };

    poll(null);
    return () => {
      stopped = true;
      window.clearTimeout(timer);
    };
  }, []);

  const running = batch !== null && !isFinished(batch.status);

  const handleCheck = async () => {
    setBusy(true);
    setError(null);
    try {
      const { data } = await previewImport();
      setPreview(data);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const handleStart = async () => {
    setBusy(true);
    setError(null);
    setReview(null);
    setResults([]);
    try {
      const { data } = await startImport();
      setPreview(data.preview);
      const { data: started } = await fetchImportProgress(data.batch_id);
      setBatch(started);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
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
      // and a town that refused must still show as pending.
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
        <p class="import-towns__hint">
          The curated roster sheet, read as a scrape. Importing raises a review
          card per town; publishing stays your decision.
        </p>
      </header>

      ${error ? html`<p class="import-error">${error}</p>` : null}
      ${resultsPanel(results)}

      ${running && batch
        ? progressPanel(batch)
        : html`
            <button
              type="button"
              class="import-action"
              ?disabled=${busy}
              @click=${handleCheck}
            >
              ${busy ? "Checking…" : "Check for changes"}
            </button>
            <import-preview
              .preview=${preview}
              .busy=${busy}
              @start-import=${handleStart}
            ></import-preview>
          `}
      ${review
        ? html`<batch-review
            .review=${review}
            .busy=${busy}
            @publish-selection=${handlePublish}
          ></batch-review>`
        : null}
    </main>
  `;
}

customElements.define("import-page", component(ImportPage, {
  useShadowDOM: false,
}));
export default ImportPage;
