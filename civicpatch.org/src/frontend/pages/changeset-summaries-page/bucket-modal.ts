// One bucket's localities, paged. A state holds thousands of jurisdictions, so this never loads
// a bucket whole — one request per page.

import { component, useEffect, useState } from "haunted";
import { html, nothing } from "lit-html";
import "../../components/basic/modal.js";
import { Pagination } from "../../components/pagination/index.js";
import { fetchStateBucket } from "../../api.js";
import { hostDispatch } from "../../utils/host-dispatch.js";
import { BUCKET_LABEL, type BucketPage, type BucketRow } from "./buckets.js";
import { jurisdictionOcdidToPath } from "../../components/ocdid-utils.js";

const PER_PAGE = 50;

const CLOSE_EVENT = "close-bucket";

type BucketModalHost = HTMLElement & {
  state: string;
  bucket: string;
  windowDays: number;
};

// `days_waiting` and `failure_reason` arrive structured, so the phrasing lives here rather than
// in the payload.
function note(row: BucketRow) {
  if (row.days_waiting != null) {
    return html`<span class="cs-bucket__note"
      >${row.days_waiting} day${row.days_waiting === 1 ? "" : "s"} waiting</span
    >`;
  }
  if (row.failure_reason) {
    return html`<span class="cs-bucket__note">${row.failure_reason}</span>`;
  }
  return nothing;
}

function CivBucketModal(host: BucketModalHost) {
  const { state, bucket, windowDays } = host;
  const [page, setPage] = useState(1);
  const [data, setData] = useState<BucketPage | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let stale = false;
    fetchStateBucket(state, bucket, PER_PAGE, (page - 1) * PER_PAGE, windowDays)
      .then((result: BucketPage) => !stale && setData(result))
      .catch((err: Error) => !stale && setError(err.message));
    return () => {
      stale = true;
    };
  }, [state, bucket, page, windowDays]);

  const close = () => hostDispatch(host, CLOSE_EVENT);
  const totalPages = data ? Math.max(1, Math.ceil(data.total / PER_PAGE)) : 1;

  const content = error
    ? html`<p class="cs-empty">${error}</p>`
    : !data
      ? html`<p class="cs-empty">Loading…</p>`
      : html`
          <div class="cs-bucket__list">
            ${data.rows.map(
              (row) => html`
                <a class="cs-bucket__item" href="/${jurisdictionOcdidToPath(row.jurisdiction_path)}">
                  <span>${row.name ?? row.jurisdiction_ocdid}</span>
                  ${note(row)}
                </a>
              `,
            )}
          </div>
          ${totalPages > 1
            ? Pagination({
                page,
                totalPages,
                onPrevious: () => setPage((n: number) => Math.max(1, n - 1)),
                onNext: () => setPage((n: number) => Math.min(totalPages, n + 1)),
                // Fixed page size: `null` is what hides the per-page selector.
                perPage: PER_PAGE,
                onPerPageChange: null,
              })
            : nothing}
        `;

  return html`
    <civ-modal
      .title=${`${state.toUpperCase()} — ${BUCKET_LABEL[bucket]}${data ? ` (${data.total})` : ""}`}
      .content=${content}
      .modalProps=${{ open: true, onClose: close, closeOnBackdropClick: true }}
    ></civ-modal>
  `;
}

customElements.define(
  "civ-bucket-modal",
  component(CivBucketModal as any, { useShadowDOM: false, observedAttributes: [] }),
);
