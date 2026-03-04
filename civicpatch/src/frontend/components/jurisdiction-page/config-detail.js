import { component, useState } from "haunted";
import { html } from "lit-html";

const DummyConfig = {
  identities: [],
};

const DummyNotes = [
  { date: "2024-01-01", content: "Information important to reviewer", pull_request_url: "<URL>" },
  { date: "2024-01-02", content: "Maybe collect comments from previous pull requests" },
];

/* Should display the config details for a jurisdiction, 
and allow users to edit and save the config. */
function ConfigDetail({ config = DummyConfig, onSave, people, notes = DummyNotes }) {
  const [isEditMode, setEditMode] = useState(false);
  const [formData, setFormData] = useState(config);
  const offices = people?.map(p => ({ "name": p.office?.name, "division_ocdid": p.office?.division_ocdid })) || [];

  const toggleEditMode = () => {
    setEditMode(!isEditMode);
  };

  const noteItem = (note) => {
    if (note.pull_request_url) {
      return html`<li><strong>${note.date}</strong>: <a href="${note.pull_request_url}" target="_blank">[View PR]</a> ${note.content} </li>`;
    }
    return html`<li><strong>${note.date}</strong>: ${note.content}</li>`;
  }

  return html`
    <article>
      <header class="d-flex align-items-center justify-content-between">
        <h2>History<h2>
        <button 
          @click=${toggleEditMode} 
          class="contrast outline"
          title="${isEditMode ? 'Switch to View Mode' : 'Switch to Edit Mode'}"
        >
          <i class="fa-solid ${isEditMode ? 'fa-eye' : 'fa-pen'}"></i>
          ${isEditMode ? 'View' : 'Edit'}
        </button>
      </header>

      <section>
        <h3>Notes</h3>
        <ul>
          ${notes.map(noteItem)}
        </ul>
      </section>
    </article>
  `;
}

customElements.define('civ-config-detail', component(ConfigDetail, {
  useShadowDOM: false,
  observedAttributes: ['config']
}));