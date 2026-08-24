// The published values of one person record, as Preview renders them.
//
// Record-level, not card-level: the jurisdiction page draws the same values from
// a plain person record with no diff card around it. Preview passes
// `card.newRecord`; nothing here knows what a PersonCard is.
//
// Split out of review-preview.ts so a consumer can have the values without
// registering the <review-preview> element.

import { html, nothing } from "lit-html";
import "./review-preview.css";
import { buildSourceUrlMap } from "../../utils/source-color-utils.js";
import { PERSON_LINK_TARGET, SOURCE_LINK_TARGET } from "../../utils/source-links.js";
import { ensureUrl } from "../fields/field-controls.js";
import {
  FIELD_SCHEMA,
  diffValue,
  type DiffRecord,
  type FieldSpec,
} from "../fields/field-model.js";

// Identity is already in the card head, so the field list is what remains.
//
// Sources ARE included, unlike the rest of the review apparatus. §11.2 originally
// excluded them as provenance rather than published data, but that put Preview at
// odds with the collapse rule, which shows source urls always precisely because
// they are the evidence behind every other value. Being able to check where a
// number came from is not review-time overhead; it is part of reading the record.
const DETAIL_FIELDS = FIELD_SCHEMA.filter(
  (field) =>
    !["image", "name", "office.name"].includes(field.key),
);

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

export type SourceMap = Map<string, { number: number; colorClass: string }>;

export function sourceMapFor(records: DiffRecord[]): SourceMap {
  const seen: { url: string }[] = [];
  const known = new Set<string>();
  for (const record of records) {
    for (const url of record?.source_urls ?? []) {
      if (url && !known.has(url)) {
        known.add(url);
        seen.push({ url });
      }
    }
  }
  return buildSourceUrlMap(seen);
}

function values(record: DiffRecord, field: FieldSpec): string[] {
  const value = diffValue(record, field);
  if (Array.isArray(value)) return value.filter(Boolean).map(String);
  const text = String(value ?? "").trim();
  return text ? [text] : [];
}

function renderLink(url: string, label: unknown, target: string, extraClass = "") {
  return html`<a
    class="review-preview__link ${extraClass}"
    href=${ensureUrl(url)}
    target=${target}
    title=${url}
    >${label}</a
  >`;
}

function renderSources(record: DiffRecord, sources: SourceMap) {
  const urls = (record?.source_urls ?? []).filter(Boolean);
  if (!urls.length) return nothing;
  return html`<span class="review-preview__value review-preview__value--sources">
    <span class="review-preview__sources-label">Sources</span>
    ${urls.map((url: string) => {
      const entry = sources.get(url);
      return entry
        ? renderLink(
            url,
            `[${entry.number}]`,
            SOURCE_LINK_TARGET,
            `review-preview__source ${entry.colorClass}`,
          )
        : nothing;
    })}
  </span>`;
}

export function renderValues(record: DiffRecord, sources: SourceMap) {
  const populated = DETAIL_FIELDS.filter((field) => field.key !== SOURCES_KEY)
    .map((field) => [field, values(record, field)] as const)
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
            ? list.map((url) => renderLink(url, url, PERSON_LINK_TARGET))
            : list.join(", ")}
        </span>
      </span>`,
    )}
    ${renderSources(record, sources)}
  `;
}
