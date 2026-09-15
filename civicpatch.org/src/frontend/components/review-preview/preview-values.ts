
import { html, nothing } from "lit-html";
import "./preview-values.css";
import { buildSourceUrlMap } from "../../utils/source-color-utils.js";
import { SOURCE_LINK_TARGET } from "../../utils/source-links.js";
import { ensureUrl } from "../fields/field-controls.js";
import {
  FIELD_SCHEMA,
  diffValue,
  POST_FIELD,
  type DiffRecord,
  type FieldSpec,
} from "../fields/field-model.js";

export const DETAIL_FIELDS = FIELD_SCHEMA.filter(
  (field) =>
    !["image", "name", "labels", POST_FIELD].includes(field.key),
);

export const SOURCES_KEY = "source_urls";

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

export function values(record: DiffRecord, field: FieldSpec): string[] {
  const value = diffValue(record, field);
  if (Array.isArray(value)) return value.filter(Boolean).map(String);
  const text = String(value ?? "").trim();
  return text ? [text] : [];
}

export function renderLink(url: string, label: unknown, target: string, extraClass = "") {
  return html`<a
    class="pc-link ${extraClass}"
    href=${ensureUrl(url)}
    target=${target}
    title=${url}
    >${label}</a
  >`;
}

export function renderSources(record: DiffRecord, sources: SourceMap) {
  const urls = (record?.source_urls ?? []).filter(Boolean);
  if (!urls.length) return nothing;
  return html`<span class="pc-value pc-value--sources">
    <span class="pc-sources-label">Sources</span>
    ${urls.map((url: string) => {
      const entry = sources.get(url);
      return entry
        ? renderLink(
            url,
            `[${entry.number}]`,
            SOURCE_LINK_TARGET,
            `pc-source ${entry.colorClass}`,
          )
        : nothing;
    })}
  </span>`;
}
