import { component, useState } from "haunted";
import { html } from "lit-html";

const DummyConfig = { identities: [] };
const DummyNotes = [
  { date: "2024-01-01", content: "Information important to reviewer", pull_request_url: "<URL>" },
  { date: "2024-01-02", content: "Maybe collect comments from previous pull requests" },
];

function ConfigDetail({ notes = DummyNotes }) {
  const [isEditMode, setEditMode] = useState(false);
  const toggleEditMode = () => setEditMode(!isEditMode);

  const noteItem = (note) => html`
    <li>
      <strong>${note.date}</strong>:
      ${note.pull_request_url
        ? html` <a href="${note.pull_request_url}" target="_blank">[View PR]</a>`
        : null}
      ${note.content}
    </li>
  `;

  return html`
    <style>
      .cd-section {
        display: flex;
        flex-direction: column;
        gap: 0.75rem;
      }
      .cd-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid var(--pico-muted-border-color);
      }
      .cd-title {
        margin: 0;
        font-size: 0.8125rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        color: var(--pico-muted-color);
      }
      .btn-toggle {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        font-size: 0.8125rem;
        font-weight: 500;
        padding: 0.3rem 0.75rem;
        border-radius: var(--pico-border-radius);
        border: 1px solid var(--pico-muted-border-color);
        background: transparent;
        color: var(--pico-muted-color);
        cursor: pointer;
        transition: border-color 0.15s, color 0.15s;
        margin: 0;
      }
      .btn-toggle:hover {
        border-color: var(--pico-color);
        color: var(--pico-color);
        background: transparent;
      }
      .cd-notes {
        margin: 0;
        padding-left: 1.25rem;
        display: flex;
        flex-direction: column;
        gap: 0.35rem;
      }
      .cd-notes li {
        font-size: 0.875rem;
        color: var(--pico-color);
        line-height: 1.5;
      }
      .cd-empty {
        font-size: 0.875rem;
        color: var(--pico-muted-color);
        margin: 0;
      }
    </style>

    <div class="cd-section">
      <div class="cd-header">
        <h4 class="cd-title">Notes</h4>
        <button class="btn-toggle" @click=${toggleEditMode}>
          <i class="fa-solid ${isEditMode ? 'fa-eye' : 'fa-pen'}"></i>
          ${isEditMode ? 'View' : 'Edit'}
        </button>
      </div>

      ${notes && notes.length > 0
        ? html`<ul class="cd-notes">${notes.map(noteItem)}</ul>`
        : html`<p class="cd-empty">No notes available.</p>`}
    </div>
  `;
}

customElements.define('civ-config-detail', component(ConfigDetail, {
  useShadowDOM: false,
  observedAttributes: ['config']
}));