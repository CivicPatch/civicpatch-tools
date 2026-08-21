import "./unmatched-text.css";
import { html } from "lit-html";
import { component } from "haunted";
import { useAsyncData } from "../../hooks/use-async-data.js";
import { fetchUnmatchedText } from "../../api.js";

// What the triage endpoint returns per row. `text` is the source's own spelling — the most
// common one where a term appears several ways — because that is what a curator searches the
// council page for.
interface UnmatchedTerm {
  text: string;
  occurrences: number;
  jurisdictions: number;
  examples: string[];
  // The one label the term came out of — not every office the person holds. Null for rows
  // written before labels were recorded; the term is still actionable, just with less context.
  example_label: string | null;
}

const PLACE_SEGMENT = /place:([^/]+)/;

// Ocdids are too long to read in a list. The place segment is the part that identifies the
// town to a person.
const placeName = (ocdid: string) => {
  const match = PLACE_SEGMENT.exec(ocdid);
  return match ? match[1].replace(/_/g, " ") : ocdid;
};

const countLabel = (count: number, noun: string) =>
  `${count} ${noun}${count === 1 ? "" : "s"}`;

function UnmatchedText() {
  const { data: terms, error } = useAsyncData<UnmatchedTerm[]>(
    () => fetchUnmatchedText().then((body) => body.data.unmatched_text),
    [],
  );

  if (error) {
    return html`<p class="unmatched-text__error">Could not load unmatched text: ${error}</p>`;
  }
  if (terms === null) {
    return html`<p class="unmatched-text__hint">Loading…</p>`;
  }
  if (terms.length === 0) {
    return html`<p class="unmatched-text__empty">
      Nothing unmatched — every label the scrapes produced resolved to a role or a designation.
    </p>`;
  }

  return html`
    <div class="unmatched-text">
      <p class="unmatched-text__hint">
        Label text that matched neither a role nor a designation. Ordered by how many
        jurisdictions it appears in: a term in many towns is one rule that fixes them all.
      </p>
      <ul class="unmatched-text__list">
        ${terms.map(
          (term) => html`
            <li class="unmatched-text__row">
              <div>
                <span class="unmatched-text__term">${term.text}</span>
                ${term.example_label
                  ? html`<p class="unmatched-text__label">“${term.example_label}”</p>`
                  : ""}
                <p class="unmatched-text__where">
                  ${term.examples.map(placeName).join(", ")}
                </p>
              </div>
              <span class="unmatched-text__reach">
                ${countLabel(term.jurisdictions, "jurisdiction")} ·
                ${countLabel(term.occurrences, "use")}
              </span>
            </li>
          `,
        )}
      </ul>
    </div>
  `;
}

customElements.define("unmatched-text", component(UnmatchedText, { useShadowDOM: false }));
