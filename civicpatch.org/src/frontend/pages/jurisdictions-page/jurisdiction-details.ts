// Jurisdiction fields, in the editor's idiom.
//
// Same row shape as a person's editor field (label / control) and the same input
// control, so a field looks and behaves the same wherever you meet it. What
// differs is the save: a person's edits accumulate and publish together, while a
// jurisdiction edit is a pull request a person merges — so it opens on an explicit
// Save rather than on every keystroke.
//
// The website and the government form are editable. The rest are shown because they
// identify the record, not because anyone edits them here.

import { html, nothing } from "lit-html";
import { component, useState, useEffect } from "haunted";
import "../../components/person-editor/person-editor.css";
import "../../components/fields/field-controls.css";
import { renderScalarNewSide } from "../../components/fields/field-controls.js";
import { urlError, type FieldSpec } from "../../components/fields/field-model.js";
import { SOURCE_LINK_TARGET } from "../../utils/source-links.js";
import { changedFields, type JurisdictionFields } from "./jurisdiction-edit.js";

const WEBSITE_FIELD: FieldSpec = { key: "url", label: "Website", type: "text" };

// The resolved government form; null when none is known yet.
interface GovernmentForm {
  value: string;
  name: string;
  description: string;
}

interface JurisdictionDetailsProps {
  data: any;
  governmentForm: GovernmentForm | null;
  // Every government form of the jurisdiction's level, for the picker.
  governmentFormOptions: GovernmentForm[];
  openPullRequestUrl: string | null;
  // The permission, not a page-wide edit mode — this widget owns its own Edit button and
  // decides on its own when to show the field as editable.
  canEditPermission: boolean;
  onSave: (changes: any) => Promise<any>;
  blockedReason: string | null;
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
    { label: "Notes", value: data?.generated_comments },
  ];
}

function renderGovernmentForm(governmentForm: GovernmentForm | null) {
  if (!governmentForm) return nothing;
  return renderRow(
    "Government form",
    html`<span class="person-editor__readonly">${governmentForm.name}</span>
      <div class="jurisdiction-details__hint">${governmentForm.description}</div>`,
  );
}

function renderGovernmentFormPicker(
  options: GovernmentForm[],
  selected: string,
  onChange: (value: string) => void,
) {
  const description = options.find((option) => option.value === selected)?.description;
  return renderRow(
    "Government form",
    html`<select @change=${(e: Event) => onChange((e.target as HTMLSelectElement).value)}>
        <option value="" .selected=${!selected}>Not known</option>
        ${options.map(
          (option) =>
            html`<option value=${option.value} .selected=${option.value === selected}>${option.name}</option>`,
        )}
      </select>
      ${description ? html`<div class="jurisdiction-details__hint">${description}</div>` : nothing}`,
  );
}

function renderWaitingPullRequest(url: string | null) {
  if (!url) return nothing;
  return html`<p class="jurisdiction-details__note">
    Pull request open:
    <a href=${url} target="_blank" rel="noopener noreferrer">${url}</a>
  </p>`;
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

function JurisdictionDetails({
  data,
  governmentForm,
  governmentFormOptions,
  openPullRequestUrl,
  canEditPermission,
  onSave,
  blockedReason,
}: JurisdictionDetailsProps) {
  const saved: JurisdictionFields = { url: data?.url ?? "", government_form: governmentForm?.value ?? "" };
  const [draft, setDraft] = useState<JurisdictionFields>(saved);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [prResult, setPrResult] = useState<any>(null);
  const [editing, setEditing] = useState(false);

  // A sync can change what is saved while the panel is open.
  useEffect(() => {
    setDraft(saved);
  }, [saved.url, saved.government_form]);

  const changes = changedFields(saved, draft);
  const hasChanges = Object.keys(changes).length > 0;
  const editDraft = (field: keyof JurisdictionFields) => (value: string) =>
    setDraft({ ...draft, [field]: value });
  const handleDiscard = () => {
    setDraft(saved);
    setEditing(false);
  };
  const cap = html`
    <div class="panel__cap">
      <b>Jurisdiction details</b>
      ${canEditPermission
        ? html`<span class="panel__cap-right">
            ${editing
              ? html`<button class="btn-quiet" @click=${handleDiscard}>
                  ${hasChanges ? "Cancel" : "Done"}
                </button>`
              : html`<button class="btn-quiet" @click=${() => setEditing(true)}>Edit</button>`}
          </span>`
        : nothing}
    </div>
    ${blockedReason
      ? html`<p class="jurisdiction-section__blocked">
          <i class="fa-solid fa-lock" aria-hidden="true"></i> ${blockedReason}
        </p>`
      : nothing}
  `;

  if (!data) return html`${cap}<p>Loading jurisdiction data…</p>`;

  const canEdit = canEditPermission && editing;
  // Clearing the website is allowed, so only a non-empty value is judged. Same
  // rule the person editor applies to a person's urls.
  const websiteError = draft.url.trim() ? urlError(draft.url.trim()) : null;

  const handleSave = async () => {
    setIsSaving(true);
    setError(null);
    try {
      // Only the changed fields: resending the others would write values nobody asked for.
      setPrResult(await onSave(changes));
      setEditing(false);
    } catch (e: any) {
      setError(e.message ?? "Failed to save.");
    } finally {
      setIsSaving(false);
    }
  };
  // The editor's scalar control saves on input; here that would open a PR per
  // keystroke, so it edits local state and Save commits.
  const website = canEdit
    ? html`${renderScalarNewSide(WEBSITE_FIELD, { url: draft.url } as any, (updates) =>
        editDraft("url")(String((updates as any).url ?? "")), { state: "same", error: websiteError }, null)}
      ${websiteError
        ? html`<div class="person-editor__error">
            <i class="fa-solid fa-triangle-exclamation"></i><span>${websiteError}</span>
          </div>`
        : nothing}`
    : data.url
      ? html`<a class="person-editor__readonly" href=${data.url} target=${SOURCE_LINK_TARGET}
          >${data.url}</a
        >`
      : html`<span class="person-editor__readonly">(none)</span>`;

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
    ${cap}
    <div class="jurisdiction-details__fields">
      ${prResult ? nothing : renderWaitingPullRequest(openPullRequestUrl)}
      ${renderRow("Website", website)}
      ${canEdit && governmentFormOptions.length
        ? renderGovernmentFormPicker(governmentFormOptions, draft.government_form, editDraft("government_form"))
        : renderGovernmentForm(governmentForm)}
      ${readOnlyRows(data).map(renderReadOnly)}
      ${renderList("Term information", terms)}
      ${renderList("Sourcing", sourcing)}
      ${renderList("Metadata", metadata)}

      ${canEdit && hasChanges
        ? html`<div class="jurisdiction-details__actions">
            <button class="btn-quiet" @click=${handleDiscard}>Discard</button>
            <button
              class="btn-primary"
              ?disabled=${isSaving || !!websiteError}
              title=${websiteError ?? ""}
              @click=${handleSave}
            >
              ${isSaving ? "Opening PR…" : "Open pull request"}
            </button>
          </div>`
        : nothing}

      ${prResult
        ? html`<p class="jurisdiction-details__note">
            Opened
            <a href=${prResult.pull_request_url} target="_blank" rel="noopener noreferrer"
              >#${prResult.pull_request_number}</a
            >.
          </p>`
        : nothing}
      ${error ? html`<p style="color: var(--diff-removed);">${error}</p>` : nothing}
    </div>
  `;
}

customElements.define(
  "civ-jurisdiction-details",
  component(JurisdictionDetails as any, { useShadowDOM: false }),
);
