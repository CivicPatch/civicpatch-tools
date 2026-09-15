import "../posts-list/posts-list.css";
import "../basic/modal.js";
import { html } from "lit-html";
import { inputValue } from "../fields/field-controls.js";
import { component, useState } from "haunted";
import { updateOrganization } from "../../api-organizations.js";
import type { Organization } from "./organizations-model.js";
import { hostDispatch } from "../../utils/host-dispatch.js";

type OrganizationEditHost = HTMLElement & {
  organization?: Organization;
};

export const SAVED_EVENT = "saved";
export const CANCEL_EVENT = "cancel";

function OrganizationEdit(host: OrganizationEditHost) {
  const organization = host.organization;
  const [name, setName] = useState(organization?.name ?? "");
  const [url, setUrl] = useState(organization?.url ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCancel = () => hostDispatch(host, CANCEL_EVENT);
  const handleName = (e: Event) => setName(inputValue(e));
  const handleUrl = (e: Event) => setUrl(inputValue(e));

  const handleSave = async () => {
    if (!organization || !name.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await updateOrganization(organization.id, {
        name: name.trim(),
        url: url.trim() || null,
      });
      hostDispatch(host, SAVED_EVENT);
    } catch (cause) {
      setError(String(cause).replace(/^Error:\s*/, ""));
      setSaving(false);
    }
  };

  const fields = html`
    <div class="post-edit">
      <label class="post-edit__field">
        <span class="post-edit__label">Name</span>
        <input type="text" .value=${name} @input=${handleName} />
      </label>
      <label class="post-edit__field">
        <span class="post-edit__label">URL</span>
        <input
          type="text"
          placeholder="optional — only if scraped separately from the jurisdiction site"
          .value=${url}
          @input=${handleUrl}
        />
      </label>
      ${error ? html`<p class="posts-list__error">${error}</p>` : ""}
    </div>
  `;

  const footer = html`
    <button class="btn btn-sm secondary" @click=${handleCancel}>Cancel</button>
    <button class="btn btn-sm" ?disabled=${saving || !name.trim()} @click=${handleSave}>
      ${saving ? "Saving…" : "Save"}
    </button>
  `;

  return html`
    <civ-modal
      .title=${"Edit organization"}
      .content=${fields}
      .footer=${footer}
      .modalProps=${{ open: true, onClose: handleCancel }}
    ></civ-modal>
  `;
}

customElements.define(
  "civ-organization-edit",
  component(OrganizationEdit, { useShadowDOM: false }),
);
