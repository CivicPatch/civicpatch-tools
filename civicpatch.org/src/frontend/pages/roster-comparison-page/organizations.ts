import { html } from "lit-html";
import type { RunOrganization } from "./types.js";

export interface OrganizationsView {
  organizations: RunOrganization[];
  compared: string[];
  onChange: (compared: string[]) => void;
}

export function organizationsPanel(view: OrganizationsView) {
  if (!view.organizations.length) return null;
  const allNames = view.organizations.map((organization) => organization.name);
  const handleChange = (name: string) => (e: Event) => {
    const checked = (e.target as HTMLInputElement).checked;
    const rest = view.compared.filter((compared) => compared !== name);
    view.onChange(checked ? [...rest, name] : rest);
  };
  const handleSelectAll = () => view.onChange(allNames);
  const handleDeselectAll = () => view.onChange([]);
  return html`<section class="panel">
    <div class="panel__cap">
      <b>organizations</b>
      <span class="panel__cap-right">${view.compared.length} of ${view.organizations.length} compared</span>
    </div>
    <div class="rc-organizations__actions">
      <button
        type="button"
        class="btn btn-sm secondary"
        ?disabled=${view.compared.length === allNames.length}
        @click=${handleSelectAll}
      >Select all</button>
      <button
        type="button"
        class="btn btn-sm secondary"
        ?disabled=${!view.compared.length}
        @click=${handleDeselectAll}
      >Deselect all</button>
    </div>
    <fieldset class="rc-organizations">
      <legend class="rc-note">
        Ticked organizations are compared: at first, every one the uploaded data matched someone in. civicpatch's
        people in the others are counted apart, outside the score.
      </legend>
      ${view.organizations.map(
        (organization) => html`<label class="rc-organization">
          <input
            type="checkbox"
            .checked=${view.compared.includes(organization.name)}
            @change=${handleChange(organization.name)}
          />
          ${organization.name}
          <span class="rc-muted">
            ${organization.matched} matched of ${organization.civicpatch_people}, in
            ${organization.jurisdictions} jurisdiction${organization.jurisdictions === 1 ? "" : "s"}
          </span>
        </label>`,
      )}
    </fieldset>
  </section>`;
}
