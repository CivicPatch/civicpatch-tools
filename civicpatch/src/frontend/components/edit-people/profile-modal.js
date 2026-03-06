import { component } from "haunted";
import { html } from "lit-html";
import "../basic/modal.js";

function renderFieldRow(label, currentValue, proposedValue, isHtml = false) {
  const changed = isHtml
    ? currentValue !== proposedValue
    : currentValue !== proposedValue;
  return html`
    <tr>
      <th>${label}</th>
      <td style=${changed ? "background: var(--pico-info-background);" : ""}>${currentValue || ""}</td>
      <td style=${changed ? "background: var(--pico-del-background);" : ""}>${proposedValue || ""}</td>
    </tr>
  `;
}

function joinOrEmpty(arr) {
  return Array.isArray(arr) && arr.length ? arr.join(", ") : "";
}

function renderLinks(arr) {
  return Array.isArray(arr) && arr.length
    ? html`<ul style="margin:0;padding-left:1.2em;">
        ${arr.map(
          url => html`<li><a href="${url}" target="_blank" rel="noopener">${url}</a></li>`
        )}
      </ul>`
    : "";
}

function ProfileModal({ open, onClose, person, existingPerson }) {
  const content = person ? html`
    <table class="pico">
      <thead>
        <tr>
          <th>Field</th>
          <th>Current</th>
          <th>Proposed</th>
        </tr>
      </thead>
      <tbody>
        ${renderFieldRow("Name", existingPerson?.name, person.name)}
        ${renderFieldRow("Email", joinOrEmpty(existingPerson?.emails), joinOrEmpty(person.emails))}
        ${renderFieldRow("Phone", joinOrEmpty(existingPerson?.phones), joinOrEmpty(person.phones))}
        ${renderFieldRow("Office", existingPerson?.office?.name, person.office?.name)}
        ${renderFieldRow("Division", existingPerson?.office?.division_ocdid, person.office?.division_ocdid)}
        ${renderFieldRow(
          "URLs",
          renderLinks(existingPerson?.urls),
          renderLinks(person.urls),
          joinOrEmpty(existingPerson?.urls) !== joinOrEmpty(person.urls)
        )}
        ${renderFieldRow(
          "Source URLs",
          renderLinks(existingPerson?.source_urls),
          renderLinks(person.source_urls),
          joinOrEmpty(existingPerson?.source_urls) !== joinOrEmpty(person.source_urls)
        )}
      </tbody>
    </table>
  ` : html`<p>No person data available.</p>`;

  function handleClose(e) {
    if (onClose) onClose(e);
  }

  return html`
    <civ-modal
      .title=${person ? `Profile: ${person.name || "Unknown"}` : "Profile"}
      .content=${content}
      .modalProps=${{ open }}
      @close=${handleClose}
    ></civ-modal>
  `;
}

customElements.define(
  "profile-modal",
  component(ProfileModal, { useShadowDOM: false })
);