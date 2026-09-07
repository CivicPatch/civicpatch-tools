import { html, TemplateResult } from "lit-html";
import type { Issue } from "./issue-row.js";
import { formatIssueType, getIssueDetail } from "./utils.js";

// Two sections over the same table machinery — a run's failure is dismissed and re-scraped, a
// person's report is read — so one component, two configurations.
export const PIPELINE_RUN_ISSUES = "pipeline_run";
export const CHANGESET_ISSUES = "changeset";

export type SectionConfig = {
  title: string;
  archivedTitle: string;
  empty: string;
  /** URL param prefix, so the two sections can be paged independently in one link. */
  urlPrefix: string;
  /** Only the pipeline side has more than one type to filter by. */
  typeFilters: boolean;
  /** What dismissing actually does, said out loud in the confirm. */
  consequence: string;
  columns: string[];
  cells: (issue: Issue) => TemplateResult;
};

export const SECTIONS: Record<string, SectionConfig> = {
  [PIPELINE_RUN_ISSUES]: {
    title: "Pipeline issues",
    archivedTitle: "Archived pipeline issues",
    empty: "No pipeline issues.",
    urlPrefix: "pipeline",
    typeFilters: true,
    consequence:
      "Their jurisdictions go back into the scrape queue, so this also means “re-scrape these”.",
    columns: ["Type", "Detail"],
    cells: (issue) => html`
      <td>
        <span class="issues-page__issue-type-chip issues-page__issue-type-chip--${issue.issue_type.replace(/_/g, "-")}">
          ${formatIssueType(issue.issue_type)}
        </span>
      </td>
      <td class="issues-page__issue-detail">${getIssueDetail(issue.data)}</td>
    `,
  },
  [CHANGESET_ISSUES]: {
    title: "Reported by reviewers",
    archivedTitle: "Archived reports",
    empty: "Nothing reported.",
    urlPrefix: "reported",
    typeFilters: false,
    consequence: "Their changesets go back into the review queue.",
    columns: ["Report"],
    cells: (issue) => html`
      <td class="issues-page__issue-report">
        <span class="issues-page__issue-report-title">${issue.data?.title ?? ""}</span>
        ${issue.data?.body
          ? html`<span class="issues-page__issue-report-body">${issue.data.body}</span>`
          : null}
      </td>
    `,
  },
};
