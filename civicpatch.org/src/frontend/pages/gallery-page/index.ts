// A catalog of the shared components, rendered live — not a second copy of their markup.
// Built because the wire demo is exactly that second copy, and today's bugs were mostly
// "fixed here, forgot to sync there." This renders the real custom elements, so nothing here
// can drift from what a page actually ships.

import { component, useState } from "haunted";
import { html } from "lit-html";
import "./gallery-page.css";
import "../../components/panel/panel.css";
import "../../components/status-badge.js";
import "../../components/confirm-modal/confirm-modal.ts";
import { Pagination } from "../../components/pagination/index.js";
import { SectionNav } from "../../components/section-nav/index.js";
// Diff-chip classes are page-scoped to activity-page — imported here, not copied, so this
// section can never show something the real page does not.
import "../activity-page/activity-page.css";

function renderSection(title: string, content: unknown) {
  return html`
    <section class="panel gallery-page__section">
      <div class="panel__cap"><b>${title}</b></div>
      <div class="gallery-page__stage">${content}</div>
    </section>
  `;
}

function renderPanel() {
  return renderSection(
    "Panel",
    html`
      <div class="panel" style="max-width: 24rem">
        <div class="panel__cap">
          <b>caption</b>
          <span class="panel__cap-right">12</span>
        </div>
        <p>Body content sits below the caption, on a hairline.</p>
      </div>
    `,
  );
}

function renderSectionNav() {
  return renderSection(
    "SectionNav",
    html`
      <div class="sectioned gallery-page__sectioned-demo">
        ${SectionNav(
          "example",
          [
            { label: "first tab", href: "#a" },
            { label: "second tab", href: "#b" },
          ],
          "#a",
        )}
        <div class="secbody">
          <p>The section body sits beside the rail.</p>
        </div>
      </div>
    `,
  );
}

function renderPagination() {
  const [page, setPage] = useState(2);
  return renderSection(
    "Pagination",
    html`
      ${Pagination({
        page,
        totalPages: 5,
        onPrevious: () => setPage(Math.max(1, page - 1)),
        onNext: () => setPage(Math.min(5, page + 1)),
        perPage: 20,
        onPerPageChange: () => {},
      })}
    `,
  );
}

function renderStatusBadges() {
  return renderSection(
    "Status badges",
    html`
      <div class="gallery-page__row">
        <civ-status-badge label="3 to review" bg="var(--warning-tint)" color="var(--warning)"></civ-status-badge>
        <civ-status-badge label="2 dismissed" bg="var(--diff-removed-bg)" color="var(--diff-removed)"></civ-status-badge>
        <civ-status-badge label="5 published" bg="var(--diff-added-bg)" color="var(--diff-added)"></civ-status-badge>
        <civ-status-badge label="1 roster edit" bg="var(--surface-2)" color="var(--text-muted)"></civ-status-badge>
      </div>
    `,
  );
}

function renderDiffChips() {
  return renderSection(
    "Diff chips (activity rows)",
    html`
      <div class="activity-row__diff">
        <span class="activity-row__chip activity-row__chip--removed">council-4@seattle.gov</span>
        <span class="activity-row__chip activity-row__chip--added">council-8@seattle.gov</span>
      </div>
      <div class="activity-row__diff" style="margin-top: 0.5rem">
        <span class="activity-row__before">Jane</span>
        <i class="fa-solid fa-arrow-right"></i>
        <span class="activity-row__after">Jane Doe</span>
      </div>
    `,
  );
}

function renderConfirmModal() {
  const [open, setOpen] = useState(false);
  return renderSection(
    "Confirm modal",
    html`
      <button class="btn btn-sm" @click=${() => setOpen(true)}>Open confirm modal</button>
      ${open
        ? html`<civ-confirm-modal
            .title=${"Scrape WA?"}
            .message=${"Scrapes every jurisdiction in WA that is due. This is example copy, not a real action."}
            .confirmLabel=${"Start scraping"}
            .variant=${"danger"}
            @confirm=${() => setOpen(false)}
            @cancel=${() => setOpen(false)}
          ></civ-confirm-modal>`
        : ""}
    `,
  );
}

function GalleryPage() {
  return html`
    <main class="gallery-page page-content">
      <div class="page-focal">
        <h1 class="page-focal__title">Components</h1>
      </div>
      ${renderPanel()}
      ${renderSectionNav()}
      ${renderPagination()}
      ${renderStatusBadges()}
      ${renderDiffChips()}
      ${renderConfirmModal()}
    </main>
  `;
}

customElements.define("gallery-page", component(GalleryPage as any, { useShadowDOM: false }));
