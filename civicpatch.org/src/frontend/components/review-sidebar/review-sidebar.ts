import "./review-sidebar.css";
import "../people-by-source/people-by-source.js";
import { html } from "lit-html";
import { component, useEffect } from "haunted";
import { isChecked, type IssueChecks } from "../review/issue-checks.js";
import { type Issue } from "../fields/field-model.js";
import { checkedCount } from "./sidebar-model.js";
import {
  hasPriorScrape,
  originSourceLabel,
  type SourceRow,
} from "../people-by-source/source-model.js";

// The card's checklist, as a drawer rather than a column in the info row. A tick
// is personal progress in this browser — never a team signal — which is why the
// note under the list says so and why ticking stays available on a read-only
// card (§8.3).
//
// A plain element, not <dialog>: the review modal renders `<dialog ?open>`
// rather than calling showModal(), which produces no ::backdrop. This ships its
// own scrim instead of inheriting that.
const CLOSE_EVENT = "close";
const TOGGLE_ISSUE_EVENT = "toggle-issue";

type ReviewSidebarHost = HTMLElement & {
  issues: Issue[];
  checks: IssueChecks;
  peopleBySource: SourceRow[];
  originSource: string | null;
  open: boolean;
};

function ReviewSidebar(host: ReviewSidebarHost) {
  const { issues = [], checks = {}, peopleBySource = [], originSource, open } = host;

  const handleClose = () =>
    host.dispatchEvent(new CustomEvent(CLOSE_EVENT, { bubbles: true, composed: true }));

  const handleToggle = (issue: Issue) =>
    host.dispatchEvent(
      new CustomEvent(TOGGLE_ISSUE_EVENT, { detail: { issue }, bubbles: true, composed: true }),
    );

  const done = checkedCount(issues, checks);

  // Esc closes, and focus goes into the drawer on open and back to whatever
  // opened it on close — otherwise a keyboard user tabs from the trigger into
  // the page behind the scrim.
  useEffect(() => {
    if (!open) return undefined;
    const opener = document.activeElement as HTMLElement | null;
    const panel = host.querySelector<HTMLElement>(".review-sidebar");
    panel?.focus();

    const handleKeydown = (e: KeyboardEvent) => {
      if (e.key === "Escape") handleClose();
    };
    document.addEventListener("keydown", handleKeydown);

    return () => {
      document.removeEventListener("keydown", handleKeydown);
      opener?.focus();
    };
  }, [open]);

  const checklistSection = () =>
    issues.length
      ? html`
          <ul class="review-sidebar__list">
            ${issues.map((issue) => {
              const ticked = isChecked(checks, issue);
              return html`
                <li class="review-sidebar__item ${ticked ? "review-sidebar__item--done" : ""}">
                  <label>
                    <input type="checkbox" .checked=${ticked} @change=${() => handleToggle(issue)} />
                    <span>${issue.message}</span>
                  </label>
                </li>
              `;
            })}
          </ul>
          <p class="review-sidebar__privacy">Only you can see these ticks.</p>
        `
      : html`<p class="review-sidebar__empty">Nothing flagged on this card.</p>`;

  return html`
    <div
      class="review-sidebar__scrim ${open ? "" : "review-sidebar__scrim--hidden"}"
      @click=${handleClose}
    ></div>
    <!-- inert rather than aria-hidden: a closed drawer is only translated off
         screen, and aria-hidden would still leave its checkboxes in the tab
         order. inert takes it out of both the focus order and the a11y tree. -->
    <aside
      class="review-sidebar ${open ? "" : "review-sidebar--closed"}"
      aria-label="Checklist"
      tabindex="-1"
      ?inert=${!open}
    >
      <div class="review-sidebar__head">
        <h4 class="review-sidebar__title">
          Checklist <span class="review-sidebar__count">${done}/${issues.length}</span>
        </h4>
        <button class="review-sidebar__toggle" @click=${handleClose} aria-label="Close checklist">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>
      <div class="review-sidebar__body">
        <!-- The ticks are the drawer's subject, so they carry no heading of
             their own — the head names them. By source is a second thing, and
             gets one. -->
        ${checklistSection()}
        <section class="review-sidebar__section">
          <h5 class="review-sidebar__section-title">Since last scrape</h5>
          ${hasPriorScrape(originSource)
            ? ""
            : html`<p class="review-sidebar__note">
                No previous scrape to compare against — the baseline is
                ${originSourceLabel(originSource)} research.
              </p>`}
          <civ-people-by-source
            .rows=${peopleBySource}
            .originSource=${originSource}
          ></civ-people-by-source>
        </section>
      </div>
    </aside>
  `;
}

customElements.define(
  "review-sidebar",
  component(ReviewSidebar as unknown as () => unknown, { useShadowDOM: false }),
);
