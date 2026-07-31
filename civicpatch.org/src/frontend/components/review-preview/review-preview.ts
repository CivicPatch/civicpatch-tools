// Preview (spec §7) — the published result, not a diff.
//
// Deliberately carries no diff vocabulary: no state colours, no strikethrough,
// no attention icons. The question it answers is "what will the site say about
// this council", and what the scrape did to get there is not part of that.
//
// Live, because it renders from the same cards Detail edits — including behind
// an open modal.

import { html, nothing } from "lit-html";
import { component } from "haunted";
import "../person-image.js";
import "./review-preview.css";
import { renderPersonRow } from "../review/person-row.js";
import { buildSourceUrlMap } from "../../utils/source-color-utils.js";
import { SOURCE_LINK_TARGET } from "../../utils/source-links.js";
import { ensureUrl } from "../review/field-controls.js";
import { FIELD_SCHEMA, diffValue, type FieldSpec } from "../review/field-model.js";
import { withDisplayImage } from "../review/field-controls.js";
import { divisionOcdidToFriendly } from "../ocdid-utils.js";
import {
  blockingErrors,
  bySeat,
  publishSet,
  PersonStatus,
  type ReviewCard,
} from "../review/review-cards.js";

interface ReviewPreviewProps {
  cards: ReviewCard[];
  jurisdictionOcdid: string | null | undefined;
  onOpenPerson: (personId: string, fieldKey: string | null) => void;
}

// Identity is already in the card head, so the field list is what remains.
//
// Sources ARE included, unlike the rest of the review apparatus. §11.2 originally
// excluded them as provenance rather than published data, but that put Preview at
// odds with the collapse rule, which shows source urls always precisely because
// they are the evidence behind every other value. Being able to check where a
// number came from is not review-time overhead; it is part of reading the record.
const DETAIL_FIELDS = FIELD_SCHEMA.filter(
  (field) =>
    !["image", "name", "office.name", "office.division_ocdid"].includes(field.key),
);

function values(card: ReviewCard, field: FieldSpec): string[] {
  const value = diffValue(card.newRecord, field);
  if (Array.isArray(value)) return value.filter(Boolean).map(String);
  const text = String(value ?? "").trim();
  return text ? [text] : [];
}

// An icon per field instead of a label: the value is what a reader is here for, and
// the label repeated down a column is noise. The name stays for screen readers.
const FIELD_ICON: Record<string, string> = {
  other_names: "id-card",
  start_date: "calendar-day",
  end_date: "calendar-xmark",
  emails: "envelope",
  phones: "phone",
  urls: "link",
};

// Sources are provenance, not a value to read: they get a word rather than an icon,
// and the numbers come from one map per card so [2] is the same page on everyone.
const SOURCES_KEY = "source_urls";

type SourceMap = Map<string, { number: number; colorClass: string }>;

function sourceMapFor(cards: ReviewCard[]): SourceMap {
  const seen: { url: string }[] = [];
  const known = new Set<string>();
  for (const card of cards) {
    for (const url of card.newRecord?.source_urls ?? []) {
      if (url && !known.has(url)) {
        known.add(url);
        seen.push({ url });
      }
    }
  }
  return buildSourceUrlMap(seen);
}

function renderLink(url: string, label: unknown, extraClass = "") {
  return html`<a
    class="review-preview__link ${extraClass}"
    href=${ensureUrl(url)}
    target=${SOURCE_LINK_TARGET}
    rel="noopener noreferrer"
    title=${url}
    >${label}</a
  >`;
}

function renderSources(card: ReviewCard, sources: SourceMap) {
  const urls = (card.newRecord?.source_urls ?? []).filter(Boolean);
  if (!urls.length) return nothing;
  return html`<span class="review-preview__value review-preview__value--sources">
    <span class="review-preview__sources-label">Sources</span>
    ${urls.map((url: string) => {
      const entry = sources.get(url);
      return entry
        ? renderLink(url, `[${entry.number}]`, `review-preview__source ${entry.colorClass}`)
        : nothing;
    })}
  </span>`;
}

function renderValues(card: ReviewCard, sources: SourceMap) {
  const populated = DETAIL_FIELDS.filter((field) => field.key !== SOURCES_KEY)
    .map((field) => [field, values(card, field)] as const)
    .filter(([, list]) => list.length > 0);

  return html`
    ${populated.map(
      ([field, list]) => html`<span class="review-preview__value">
        <i
          class="fa-solid fa-${FIELD_ICON[field.key] ?? "circle-info"}"
          aria-hidden="true"
        ></i>
        <span class="visually-hidden">${field.label}</span>
        <span class="review-preview__value-text">
          ${field.key === "urls"
            ? list.map((url) => renderLink(url, url))
            : list.join(", ")}
        </span>
      </span>`,
    )}
    ${renderSources(card, sources)}
  `;
}

// Not clickable: this is the published record, so the values are plain selectable
// text you can copy field by field. Nothing here opens an editor.
function renderCard(card: ReviewCard, sources: SourceMap) {
  const record = card.newRecord;
  const division = divisionOcdidToFriendly(record?.office?.division_ocdid ?? "") || "";
  const office = [record?.office?.name, division].filter(Boolean).join(" · ");

  return renderPersonRow({
    record,
    name: record?.name || "(unnamed)",
    subtitle: office,
    // Status tints the card here too. Preview still carries no other diff
    // vocabulary — no badge, no strikethrough, no attention icon — so the tint is
    // the one cue, and only ever a background.
    modifier: card.status,
    meta: renderValues(card, sources),
  });
}

function ReviewPreview(props: ReviewPreviewProps) {
  const { cards, jurisdictionOcdid } = props;
  const publishing = publishSet(cards ?? []);
  const ordered = bySeat(publishing, jurisdictionOcdid);
  const blockers = blockingErrors(cards ?? []);
  const sources = sourceMapFor(publishing);

  const added = publishing.filter((c) => c.status === PersonStatus.ADDED).length;
  // Everyone with a record who is not being published — the scrape lost them or
  // the reviewer dropped them. Both are "dropped" from the roster's point of view.
  const dropped = (cards ?? []).length - publishing.length;

  return html`
    <div class="review-preview">
      <div class="review-preview__bar">
        <span class="review-preview__count">
          ${ordered.length} official${ordered.length === 1 ? "" : "s"} will be published
        </span>
        <span class="review-preview__sub">
          ${added} new · ${dropped} dropped
        </span>
      </div>

      ${blockers.length
        ? html`<div class="review-preview__blockers">
            <span class="review-preview__blockers-title">
              ${blockers.length} thing${blockers.length === 1 ? "" : "s"} to fix before publishing
            </span>
            <ul>
              ${blockers.map(
                (blocker) => html`<li>
                  ${blocker.name} — ${blocker.fieldLabel}: ${blocker.message}
                </li>`,
              )}
            </ul>
          </div>`
        : nothing}

      ${ordered.length
        ? html`<div class="review-preview__grid">
            ${ordered.map((card) => renderCard(card, sources))}
          </div>`
        : html`<p class="review-preview__empty">
            This card would publish an empty roster.
          </p>`}
    </div>
  `;
}

customElements.define(
  "review-preview",
  component(ReviewPreview as unknown as () => unknown, { useShadowDOM: false }),
);
