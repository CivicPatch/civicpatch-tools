import "../../../components/panel/panel.css";
import "./active-runs.css";
import "../../../components/action-btn/action-btn.css";
import { html } from "lit-html";
import { component, useState } from "haunted";
import { ref } from "lit/directives/ref.js";
import { durationBetween } from "../../../utils/date-utils.js";
import { Pagination } from "../../../components/pagination/index.js";
import { cancelPipelineRun } from "../../../api.js";
import { jurisdictionOcdidToPath } from "../../../components/ocdid-utils.js";
import { usePagerRef } from "../../../hooks/use-pager-ref.ts";

// Rows, not a table: every column but the name is fixed width, so a grid keeps them
// aligned down the page without a <table>'s header furniture. Follows the demo's
// in-flight row — status, who, how far, how long, and the one control.
function ActiveRuns({ jobs, page = 1, totalPages = 1, perPage = 25, onPageChange, onPerPageChange, onCancel, canCancel }) {
  const [cancellingIds, setCancellingIds] = useState(new Set());
  const { listRef, scrollToTop } = usePagerRef();

  if (!jobs || jobs.length === 0) return null;

  const handleCancel = async (pipelineRunId) => {
    setCancellingIds(prev => new Set(prev).add(pipelineRunId));
    try {
      await cancelPipelineRun(pipelineRunId);
      if (onCancel) onCancel(pipelineRunId);
    } catch (_) {
      // noop — leave the row visible so the user can retry
    } finally {
      setCancellingIds(prev => {
        const next = new Set(prev);
        next.delete(pipelineRunId);
        return next;
      });
    }
  };

  const row = (job) => {
    const cancelling = cancellingIds.has(job.pipeline_run_id);
    const status = cancelling ? "CANCELLING" : (job.status || "");
    return html`
      <div class="run-row ${cancelling ? "run-row--cancelling" : ""}">
        <span class="run-row__status run-row__status--${status.toLowerCase()}">${status}</span>
        <span class="run-row__who">
          <a class="run-row__name" href="/${jurisdictionOcdidToPath(job.jurisdiction_path)}"
            >${job.jurisdiction_name || job.jurisdiction_ocdid}</a
          >
          <span class="run-row__sub"
            ><span class="run-row__state">${job.state}</span
            ><span class="run-row__id">${job.pipeline_run_id}</span></span
          >
        </span>
        <span class="run-row__bar"><i style="width:${job.progress ?? 0}%"></i></span>
        <span class="run-row__pct">${job.progress ?? 0}%</span>
        <span class="run-row__age">${durationBetween(job.created_at, job.updated_at)}</span>
        ${canCancel
          ? html`<button class="civ-action-btn civ-action-btn--danger" ?disabled=${cancelling}
              @click=${() => handleCancel(job.pipeline_run_id)}
            >${cancelling ? "cancelling" : "cancel"}</button>`
          : html`<span></span>`}
      </div>
    `;
  };

  // Built once so Next/Previous re-orients to the top of the list either way — clicking
  // the bottom pager most often leaves the reader below what just changed above them.
  const pager = Pagination({
    page,
    totalPages,
    onPrevious: () => {
      onPageChange(page - 1);
      scrollToTop();
    },
    onNext: () => {
      onPageChange(page + 1);
      scrollToTop();
    },
    perPage,
    onPerPageChange,
  });

  return html`
    <section class="panel" ${ref(listRef)}>
      <div class="panel__cap">
        <b>runs</b>
        <span class="panel__cap-right">${jobs.length} on this page</span>
      </div>
      ${pager}
      ${jobs.map(row)}
      ${pager}
    </section>
  `;
}

customElements.define("pipeline-runs-list", component(ActiveRuns, { useShadowDOM: false }));
