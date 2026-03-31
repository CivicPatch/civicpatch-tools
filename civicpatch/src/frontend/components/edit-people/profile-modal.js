import { component } from "haunted";
import { html } from "lit-html";
import "../basic/modal.js";
import "../person-image.js";

function renderFieldRow(label, currentValue, proposedValue, changed) {
  const isChanged = changed !== undefined ? changed : currentValue !== proposedValue;
  return html`
    <tr>
      <th>${label}</th>
      <td style=${isChanged ? "background: var(--pico-info-background);" : ""}>${currentValue || ""}</td>
      <td style=${isChanged ? "background: var(--pico-del-background);" : ""}>${proposedValue || ""}</td>
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

function renderImageRow(label, currentPerson, proposedPerson) {
  const isChanged = (currentPerson?.cdn_image || currentPerson?.image) !== (proposedPerson?.cdn_image || proposedPerson?.image);
  return html`
    <tr>
      <th>${label}</th>
      <td style=${isChanged ? "background: var(--pico-info-background);" : ""}>
        <person-image .person=${currentPerson}></person-image>
      </td>
      <td style=${isChanged ? "background: var(--pico-del-background);" : ""}>
        <person-image .person=${proposedPerson}></person-image>
      </td>
    </tr>
  `;
}

function renderReadOnlyContent(person) {
  if (!person) return html`<p>No person data available.</p>`;
  return html`
    <table class="pico">
      <tbody>
        <tr><th>Image</th><td><person-image .person=${person}></person-image></td></tr>
        <tr><th>Name</th><td>${person.name || ""}</td></tr>
        <tr><th>Other Names</th><td>${joinOrEmpty(person.other_names)}</td></tr>
        <tr><th>Office</th><td>${person.office?.name || ""}</td></tr>
        <tr><th>Division</th><td>${person.office?.division_ocdid || ""}</td></tr>
        <tr><th>Email</th><td>${joinOrEmpty(person.emails)}</td></tr>
        <tr><th>Phone</th><td>${joinOrEmpty(person.phones)}</td></tr>
        <tr><th>Start Date</th><td>${person.start_date || ""}</td></tr>
        <tr><th>End Date</th><td>${person.end_date || ""}</td></tr>
        <tr><th>URLs</th><td>${renderLinks(person.urls)}</td></tr>
        <tr><th>Source URLs</th><td>${renderLinks(person.source_urls)}</td></tr>
        <tr><th>Updated At</th><td>${person.updated_at || ""}</td></tr>
      </tbody>
    </table>
  `;
}

function ProfileModal({ open, onClose, person, existingPerson, nameMatches = [], searchSuggestions = [], readOnly = false }) {
  function handleLink(e, matchedId) {
    e.target.dispatchEvent(new CustomEvent("link-person", {
      detail: { personId: matchedId },
      bubbles: true,
    }));
  }

  const linkSuggestions = nameMatches.length
    ? html`
      <section class="profile-modal__link-suggestions">
        <p><strong>Possible existing matches</strong> — link to copy their ID onto this person:</p>
        <ul class="profile-modal__match-list">
          ${nameMatches.map(m => html`
            <li class="profile-modal__match-item">
              <person-image .person=${m}></person-image>
              <span>${m.name}</span>
              <button
                type="button"
                class="secondary btn-sm"
                @click=${(e) => handleLink(e, m.id)}
              >Link</button>
            </li>
          `)}
        </ul>
      </section>
    `
    : "";

  const searchSuggestionsSection = person?._isNew && searchSuggestions.length
    ? html`
      <section class="profile-modal__search-suggestions">
        <p><strong>Suggested profiles</strong> — link this person to an existing record:</p>
        <ul class="profile-modal__match-list">
          ${searchSuggestions.map(m => html`
            <li class="profile-modal__match-item">
              <person-image .person=${m}></person-image>
              <span>${m.name}</span>
              <span>${[m.office?.name, m.office?.division_ocdid].filter(Boolean).join(" — ")}</span>
              <button
                type="button"
                class="secondary btn-sm"
                @click=${(e) => handleLink(e, m.id)}
              >Link</button>
            </li>
          `)}
        </ul>
      </section>
    `
    : "";

  const content = readOnly
    ? renderReadOnlyContent(person)
    : person ? html`
    ${searchSuggestionsSection}
    ${linkSuggestions}
    <table class="pico">
      <thead>
        <tr>
          <th>Field</th>
          <th>Current</th>
          <th>Proposed</th>
        </tr>
      </thead>
      <tbody>
        ${renderImageRow("Image", existingPerson, person)}
        ${renderFieldRow("Name", existingPerson?.name, person.name)}
        ${renderFieldRow("Other Names", joinOrEmpty(existingPerson?.other_names), joinOrEmpty(person.other_names))}
        ${renderFieldRow("Email", joinOrEmpty(existingPerson?.emails), joinOrEmpty(person.emails))}
        ${renderFieldRow("Phone", joinOrEmpty(existingPerson?.phones), joinOrEmpty(person.phones))}
        ${renderFieldRow("Office", existingPerson?.office?.name, person.office?.name)}
        ${renderFieldRow("Division", existingPerson?.office?.division_ocdid, person.office?.division_ocdid)}
        ${renderFieldRow("Start Date", existingPerson?.start_date, person.start_date)}
        ${renderFieldRow("End Date", existingPerson?.end_date, person.end_date)}
        ${renderFieldRow(
          "URLs",
          renderLinks(existingPerson?.urls),
          renderLinks(person.urls),
          joinOrEmpty(existingPerson?.urls) !== joinOrEmpty(person.urls),
        )}
        ${renderFieldRow(
          "Source URLs",
          renderLinks(existingPerson?.source_urls),
          renderLinks(person.source_urls),
          joinOrEmpty(existingPerson?.source_urls) !== joinOrEmpty(person.source_urls),
        )}
        ${renderFieldRow("Updated At", existingPerson?.updated_at, person.updated_at)}
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
