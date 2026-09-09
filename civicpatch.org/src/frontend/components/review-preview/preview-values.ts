
import { html, nothing } from "lit-html";
import "./review-preview.css";
import { buildSourceUrlMap } from "../../utils/source-color-utils.js";
import { PERSON_LINK_TARGET, SOURCE_LINK_TARGET } from "../../utils/source-links.js";
import { ensureUrl } from "../fields/field-controls.js";
import {
  FIELD_SCHEMA,
  diffValue,
  POST_FIELD,
  type DiffRecord,
  type FieldSpec,
} from "../fields/field-model.js";

const DETAIL_FIELDS = FIELD_SCHEMA.filter(
  (field) =>
    !["image", "name", "labels", POST_FIELD].includes(field.key),
);

const FIELD_ICON: Record<string, string> = {
  other_names: "id-card",
  start_date: "calendar-day",
  end_date: "calendar-xmark",
  emails: "envelope",
  phones: "phone",
  urls: "link",
};

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
