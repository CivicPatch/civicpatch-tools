import "./posts-list.css";
import { html } from "lit-html";
import { component, useState } from "haunted";
import { updatePost } from "../../api.js";
import type { PostRow } from "./posts-model.js";

type PostEditHost = HTMLElement & {
  post?: PostRow;
};

export const SAVED_EVENT = "saved";
export const CANCEL_EVENT = "cancel";

// Only what a person owns. Role and division are the post's identity — changing either would
// make the next scrape mint a second post rather than match this one — and `status` was
// dropped in migration 121, since whether a post is vouched for follows from having members.
function PostEdit(host: PostEditHost) {
  const post = host.post;
  const [label, setLabel] = useState(post?.label ?? "");
  const [headcount, setHeadcount] = useState(String(post?.headcount ?? 1));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const emit = (name: string) =>
    host.dispatchEvent(new CustomEvent(name, { bubbles: true, composed: true }));

  const handleCancel = () => emit(CANCEL_EVENT);

  const handleLabelInput = (e: Event) => setLabel((e.target as HTMLInputElement).value);
  const handleHeadcountInput = (e: Event) =>
    setHeadcount((e.target as HTMLInputElement).value);

  const handleSave = async () => {
    if (!post) return;
    setSaving(true);
    setError(null);
    try {
      // Blank clears the label back to the derived name rather than storing "".
      await updatePost(post.id, {
        label: label.trim() || null,
        headcount: Number(headcount),
      });
      emit(SAVED_EVENT);
    } catch (cause) {
      setError(String(cause));
      setSaving(false);
    }
  };

  return html`
    <div class="post-edit">
      <label class="post-edit__field">
        <span class="post-edit__label">Label</span>
        <input
          type="text"
          .value=${label}
          placeholder="derived from role and division"
          @input=${handleLabelInput}
        />
      </label>
      <label class="post-edit__field">
        <span class="post-edit__label">Headcount</span>
        <input type="number" min="1" .value=${headcount} @input=${handleHeadcountInput} />
      </label>
      ${error ? html`<p class="posts-list__error">${error}</p>` : ""}
      <div class="post-edit__actions">
        <button class="action-btn" ?disabled=${saving} @click=${handleSave}>
          ${saving ? "Saving…" : "Save"}
        </button>
        <button class="action-btn action-btn--muted" @click=${handleCancel}>Cancel</button>
      </div>
    </div>
  `;
}

customElements.define("civ-post-edit", component(PostEdit, { useShadowDOM: false }));
