import { html, nothing } from "lit-html";
import "../../components/person-image.js";
import { type ReviewPerson } from "./import-types.js";

// The jurisdiction page's directory row, smaller. A bulk review is a scan across many
// localities, so this is the same shape at a tighter scale rather than the full review card.

function contact(person: ReviewPerson) {
  const first = (values: string[]) => values[0];
  return html`
    <div class="review-person__contact">
      ${person.emails.length
        ? html`<a href="mailto:${first(person.emails)}"
            >${first(person.emails)}</a
          >`
        : nothing}
      ${person.phones.length
        ? html`<a href="tel:${first(person.phones)}">${first(person.phones)}</a>`
        : nothing}
      ${person.urls.length
        ? html`<a
            href=${first(person.urls)}
            target="_blank"
            rel="noopener noreferrer"
            class="secondary"
            >Website</a
          >`
        : nothing}
    </div>
  `;
}

function term(person: ReviewPerson) {
  if (!person.start_date && !person.end_date) return nothing;
  return html`<span class="review-person__term"
    >${person.start_date ?? "?"} to ${person.end_date ?? "?"}</span
  >`;
}

/**
 * A warning, not an error: an unresolved title still mints a post, but it is the row a curator
 * most needs to look at before publishing.
 */
function unmatched(person: ReviewPerson) {
  if (person.role_id && !person.unmatched_text.length) return nothing;
  const wording = person.unmatched_text.join(", ");
  return html`<span class="review-unmatched"
    >${person.role_id
      ? `unmatched: ${wording}`
      : `no role${wording ? `: ${wording}` : ""}`}</span
  >`;
}

export function renderReviewPerson(person: ReviewPerson) {
  return html`
    <div class="review-person">
      <person-image .person=${person} .size=${"2.1rem"}></person-image>
      <div class="review-person__info">
        <p class="review-person__name">${person.name}</p>
        <p class="review-person__office">
          ${person.label || nothing} ${unmatched(person)} ${term(person)}
        </p>
        ${contact(person)}
      </div>
    </div>
  `;
}
