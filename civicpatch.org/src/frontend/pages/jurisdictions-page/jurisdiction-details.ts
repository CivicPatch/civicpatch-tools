// Jurisdiction fields, in the editor's idiom.
//
// Same row shape as a person's editor field (label / control) and the same input
// control, so a field looks and behaves the same wherever you meet it. What
// differs is the save: a person's edits accumulate and publish together, while a
// jurisdiction url patch is its own PR — so it commits on an explicit Save rather
// than on every keystroke.
//
// Only the website is editable. The rest are shown because they identify the
// record, not because anyone edits them here.

import { html, nothing } from "lit-html";
import { component, useState, useEffect } from "haunted";
import "../../components/person-editor/person-editor.css";
import "../../components/review/field-controls.css";
import { renderScalarNewSide } from "../../components/review/field-controls.js";
import { urlError, type FieldSpec } from "../../components/review/field-model.js";
import { SOURCE_LINK_TARGET } from "../../utils/source-links.js";

const WEBSITE_FIELD: FieldSpec = { key: "url", label: "Website", type: "text" };

interface JurisdictionDetailsProps {
  data: any;
  canEdit: boolean;
  onSave: (form: any) => Promise<any>;
}

interface ReadOnlyRow {
  label: string;
  value: unknown;
  href?: string | null;
}

function readOnlyRows(data: any): ReadOnlyRow[] {
  return [
    { label: "Wikipedia", value: data?.wiki_url, href: data?.wiki_url },
    { label: "Population", value: data?.population?.toLocaleString?.() },
    { label: "GEOID", value: data?.geoid },
    { label: "Classification", value: data?.classification },
    { label: "OCD ID", value: data?.id },
  ];
}

function renderRow(label: string, control: unknown) {
  return html`
    <div class="person-editor__field">
      <div class="person-editor__label">${label}</div>
      <div class="person-editor__control">${control}</div>
    </div>
  `;
}

function renderReadOnly(row: ReadOnlyRow) {
  if (!row.value) return nothing;
  const control = row.href
    ? html`<a class="person-editor__readonly" href=${row.href} target=${SOURCE_LINK_TARGET}
        >${row.value}</a
      >`
    : html`<span class="person-editor__readonly">${row.value}</span>`;
  return renderRow(row.label, control);
}

// Term, sourcing and metadata are unchanged from the previous panel — shown when
// present, and deliberately not cut (see the spec's §2.1).
function renderList(title: string, rows: [string, unknown][][]) {
  if (!rows.length) return nothing;
  return html`
    <div class="jurisdiction-details__group">
      <h4 class="jurisdiction-details__group-title">${title}</h4>
      ${rows.map(
        (entry) => html`<div class="jurisdiction-details__group-item">
          ${entry.map(([label, value]) =>
            value ? renderRow(label, html`<span class="person-editor__readonly">${value}</span>`) : nothing,
          )}
        </div>`,
      )}
    </div>
  `;
}

function JurisdictionDetails({ data, canEdit, onSave }: JurisdictionDetailsProps) {
  const [url, setUrl] = useState<string>(data?.url ?? "");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [prResult, setPrResult] = useState<any>(null);

  useEffect(() => {
    setUrl(data?.url ?? "");
  }, [data?.url]);

  if (!data) return html`<p>Loading jurisdiction data…</p>`;

  const dirty = (url ?? "") !== (data.url ?? "");
  // Clearing the website is allowed, so only a non-empty value is judged. Same
  // rule the person editor applies to a person's urls.
  const websiteError = url.trim() ? urlError(url.trim()) : null;

  const handleSave = async () => {
    setIsSaving(true);
    setError(null);
    try {
      setPrResult(await onSave({ ...data, url }));
    } catch (e: any) {
      setError(e.message ?? "Failed to save.");
    } finally {
      setIsSaving(false);
    }
  };

  // The editor's scalar control saves on input; here that would open a PR per
  // keystroke, so it edits local state and Save commits.
  const website = canEdit
    ? html`${renderScalarNewSide(WEBSITE_FIELD, { url } as any, (updates) =>
        setUrl(String((updates as any).url ?? "")), { state: "same", error: websiteError }, null)}
      ${websiteError
        ? html`<div class="person-editor__error">
            <i class="fa-solid fa-triangle-exclamation"></i><span>${websiteError}</span>
          </div>`
        : nothing}`
    : data.url
      ? html`<a class="person-editor__readonly" href=${data.url} target=${SOURCE_LINK_TARGET}
          >${data.url}</a
        >`
      : html`<span class="person-editor__readonly">—</span>`;

  const terms = (data.term ?? []).map((t: any) => [
    ["Duration", t.duration ? `${t.duration} years` : null],
    ["Description", t.term_description],
    ["Positions", t.number_of_positions],
    ["Term limits", t.term_limits],
    ["Last term end", t.last_known_term_end_date],
  ] as [string, unknown][]);

  const sourcing = (data.sourcing ?? []).map((s: any) => [
    ["Field", s.field],
    ["Source", s.source_name],
    ["Source url", s.source_url],
    ["Source type", s.source_type],
  ] as [string, unknown][]);

  const metadata = (data.metadata?.urls ?? []).map((u: string) => [["URL", u]] as [string, unknown][]);

  return html`
    <div class="jurisdiction-details__fields">
      ${renderRow("Website", website)}
      ${readOnlyRows(data).map(renderReadOnly)}
      ${renderList("Term information", terms)}
      ${renderList("Sourcing", sourcing)}
      ${renderList("Metadata", metadata)}

      ${canEdit && dirty
        ? html`<div class="jurisdiction-details__actions">
            <button class="btn-quiet" @click=${() => setUrl(data.url ?? "")}>Discard</button>
            <button
              class="btn-primary"
              ?disabled=${isSaving || !!websiteError}
              title=${websiteError ?? ""}
              @click=${handleSave}
            >
              ${isSaving ? "Opening PR…" : "Save website"}
            </button>
          </div>`
        : nothing}

      ${prResult
        ? html`<p class="jurisdiction-details__note">
            Opened
            <a href=${prResult.pull_request_url} target="_blank" rel="noopener noreferrer"
              >#${prResult.pull_request_number}</a
            >. It merges and syncs in the background — reload in a moment to see it
            here.
          </p>`
        : nothing}
      ${error ? html`<p style="color: var(--pico-del-color);">${error}</p>` : nothing}
    </div>
  `;
}

customElements.define(
  "civ-jurisdiction-details",
  component(JurisdictionDetails as any, { useShadowDOM: false }),
);
