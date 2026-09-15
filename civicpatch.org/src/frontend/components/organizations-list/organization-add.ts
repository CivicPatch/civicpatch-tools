import "../posts-list/posts-list.css";
import "../basic/modal.js";
import { html } from "lit-html";
import { inputValue } from "../fields/field-controls.js";
import { component, useState } from "haunted";
import { createOrganization } from "../../api-organizations.js";
import { hostDispatch } from "../../utils/host-dispatch.js";

type OrganizationAddHost = HTMLElement & {
  jurisdictionOcdid?: string;
};

export const ADDED_EVENT = "added";
export const CANCEL_EVENT = "cancel";

function OrganizationAdd(host: OrganizationAddHost) {
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCancel = () => hostDispatch(host, CANCEL_EVENT);
  const handleName = (e: Event) => setName(inputValue(e));
  const handleUrl = (e: Event) => setUrl(inputValue(e));

  const handleSave = async () => {
    if (!host.jurisdictionOcdid || !name.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await createOrganization(host.jurisdictionOcdid, {
        name: name.trim(),
        url: url.trim() || null,
      });
      hostDispatch(host, ADDED_EVENT);
    } catch (cause) {
      setError(String(cause).replace(/^Error:\s*/, ""));
      setSaving(false);
    }
  };

  const fields = html`
    <div class="post-edit">
      <label class="post-edit__field">
        <span class="post-edit__label">Name</span>
        <input
          type="text"
          placeholder="Municipal Court"
          .value=${name}
          @input=${handleName}
        />
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
      ${saving ? "Adding…" : "Add"}
    </button>
  `;

  return html`
    <civ-modal
      .title=${"Add organization"}
      .content=${fields}
      .footer=${footer}
      .modalProps=${{ open: true, onClose: handleCancel }}
    ></civ-modal>
  `;
}

customElements.define(
  "civ-organization-add",
  component(OrganizationAdd, { useShadowDOM: false }),
);
