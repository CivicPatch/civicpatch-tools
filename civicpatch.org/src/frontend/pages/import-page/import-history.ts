import { html } from "lit-html";
import { component } from "haunted";
import { BATCH_FAILED, type ImportProgress } from "./import-types.js";

// Past imports, newest first. A row opens that batch's own review rather than the latest one,
// which is what makes an import from an hour ago still answerable.

const OPEN_EVENT = "open-batch";

type ImportHistoryHost = HTMLElement & {
  batches: ImportProgress[];
  currentBatchId: string | null;
};

function when(value: string | null): string {
  if (!value) return "-";
  return new Date(value).toLocaleString();
}

function ImportHistory(host: ImportHistoryHost) {
  const batches = host.batches ?? [];
  if (!batches.length) {
    return html`<p class="import-hint">No imports yet.</p>`;
  }

  const row = (batch: ImportProgress) => {
    const open = () =>
      host.dispatchEvent(
        new CustomEvent(OPEN_EVENT, {
          detail: { batch_id: batch.batch_id },
          bubbles: true,
          composed: true,
        }),
      );
    return html`
      <tr class=${batch.batch_id === host.currentBatchId ? "import-history--current" : ""}>
        <td>${when(batch.started_at)}</td>
        <td>
          ${batch.status}
          ${batch.status === BATCH_FAILED && batch.error
            ? html`<span class="import-history__error">${batch.error}</span>`
            : null}
        </td>
        <td class="import-history__count">
          ${batch.items_done}${batch.items_total == null
            ? ""
            : ` / ${batch.items_total}`}
        </td>
        <td>
          <button type="button" class="import-link btn-ghost" @click=${open}>
            Open
          </button>
        </td>
      </tr>
    `;
  };

  return html`
    <table class="import-history">
      <thead>
        <tr>
          <th>Started</th>
          <th>Status</th>
          <th>Localities</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        ${batches.map(row)}
      </tbody>
    </table>
  `;
}

customElements.define(
  "import-history",
  component(ImportHistory as unknown as () => unknown, {
    useShadowDOM: false,
  }),
);
