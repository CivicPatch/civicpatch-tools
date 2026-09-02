import "./posts-list.css";
import "../basic/modal.js";
import { html } from "lit-html";
import { inputValue } from "../fields/field-controls.js";
import { component, useState } from "haunted";
import { updatePost } from "../../api.js";
import { divisionName, divisionKey } from "./posts-model.js";
import type { PostRow } from "./posts-model.js";
import { hostDispatch } from "../../utils/host-dispatch.js";

type PostEditHost = HTMLElement & {
  post?: PostRow;
};

export const SAVED_EVENT = "saved";
export const CANCEL_EVENT = "cancel";

// Only what a person owns. Role and division are the post's identity — changing either would
// make the next scrape mint a second post rather than match this one; `status` was dropped in
// migration 121, since whether a post is vouched for follows from having members; and `label`
// in 148, since it is composed from the role and the division on read.
function PostEdit(host: PostEditHost) {
  const post = host.post;
  const [headcount, setHeadcount] = useState(String(post?._headcount ?? 1));
  const [isTracked, setIsTracked] = useState(post?._is_tracked ?? true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCancel = () => hostDispatch(host, CANCEL_EVENT);

  const handleHeadcountInput = (e: Event) =>
    setHeadcount(inputValue(e));
  const handleTrackedChange = (e: Event) =>
    setIsTracked((e.target as HTMLInputElement).checked);

  const handleSave = async () => {
    if (!post) return;
    setSaving(true);
    setError(null);
    try {
      await updatePost(post.id, {
        headcount: Number(headcount),
        isTracked,
      });
      hostDispatch(host, SAVED_EVENT);
    } catch (cause) {
      setError(String(cause));
      setSaving(false);
    }
  };

  const fields = html`
    <div class="post-edit">
      <p class="post-edit__subject">
        ${post?.label}, ${divisionName(post?.division_ocdid ?? "")}
        <span class="post-edit__key">${divisionKey(post?.division_ocdid ?? "")}</span>
      </p>
      <label class="post-edit__field">
        <span class="post-edit__label">Headcount</span>
        <input type="number" min="1" .value=${headcount} @input=${handleHeadcountInput} />
      </label>
      <label class="post-edit__field post-edit__field--check">
        <input type="checkbox" .checked=${isTracked} @change=${handleTrackedChange} />
        <span class="post-edit__label">Tracked</span>
      </label>
      <p class="post-edit__hint">
        A tracked post is one we follow: a roster that stops naming its holder is worth
        someone's attention. Untrack the offices this jurisdiction does not elect — they stay
        recorded, they just stop asking for review.
      </p>
      ${error ? html`<p class="posts-list__error">${error}</p>` : ""}
    </div>
  `;

  const footer = html`
    <button class="btn btn-sm secondary" @click=${handleCancel}>Cancel</button>
    <button class="btn btn-sm" ?disabled=${saving} @click=${handleSave}>
      ${saving ? "Saving…" : "Save"}
    </button>
  `;

  return html`
    <civ-modal
      .title=${"Edit post"}
      .content=${fields}
      .footer=${footer}
      .modalProps=${{ open: true, onClose: handleCancel }}
    ></civ-modal>
  `;
}

customElements.define("civ-post-edit", component(PostEdit, { useShadowDOM: false }));
