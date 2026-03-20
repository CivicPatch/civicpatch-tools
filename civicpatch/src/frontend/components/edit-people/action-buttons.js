import { component } from 'haunted';
import { html } from 'lit-html';

const TERMINAL_STATUSES = ["merged", "closed", "error"];

function PeopleActionButtons({
  onAdd,
  onMerge,
  onBulkDelete,
  onReset,
  onSubmit,
  onPublish,
  onClosePR,
  selectedPeople,
  dirty,
  hasPullRequest,
  prStatus,
}) {
  const isTerminal = TERMINAL_STATUSES.includes(prStatus);
  const isPublishing = prStatus === "loading_merge";
  const isClosing = prStatus === "loading_close";

  return html`
    <div class="action-buttons">
      <button @click=${onAdd} class="secondary btn-sm">Add</button>
      <button @click=${onMerge} ?disabled=${selectedPeople.length < 2} class="secondary btn-sm">
        Merge (${selectedPeople.length})
      </button>
      <button @click=${onBulkDelete} ?disabled=${selectedPeople.length === 0} class="secondary btn-sm">
        Delete (${selectedPeople.length})
      </button>
      <button @click=${onReset} ?disabled=${dirty === false} class="secondary btn-sm action-buttons__reset">
        Reset
      </button>
      <button @click=${onSubmit} ?disabled=${dirty === false} class="btn-sm">
        Submit
      </button>
      ${hasPullRequest ? html`
        <button @click=${onClosePR} ?disabled=${isTerminal || isPublishing || isClosing} class="destructive btn-sm">
          ${isClosing ? "Closing..." : prStatus === "closed" ? "Closed" : "Close PR"}
        </button>
        <button @click=${onPublish} ?disabled=${isTerminal || isPublishing || isClosing} class="btn-sm">
          ${isPublishing ? "Publishing..." : prStatus === "merged" ? "Published" : "Publish"}
        </button>
      ` : ""}
    </div>
  `;
}

customElements.define('civ-people-action-buttons', component(PeopleActionButtons, {
  useShadowDOM: false,
  observedAttributes: ['jurisdiction_ocdid']
}));
