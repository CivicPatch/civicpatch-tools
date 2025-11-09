import { component } from "haunted";
import { html } from "lit-html";

function PeopleList({ local = [] }) {
    const people = local;

    // Helper: Formats array items (Divisions)
    const formatArray = (arr) => arr && arr.length > 0
        ? arr.map(item => html`<span class="badge" style="margin-right: 0.25rem;">${item}</span>`)
        : html`<small>N/A</small>`;

    // Helper: Formats Sources as [1], [2], [3]
    const formatSources = (sources) => {
        if (!sources || sources.length === 0) {
            return html`<small>No Sources</small>`;
        }
        
        return html`
            <div style="line-height: 1.2; font-size: 0.8rem;">
                ${sources.map((source, index) => html`
                    <a 
                        href="${source}" 
                        target="_blank" 
                        title="${source}" 
                        style="margin-right: 0.25rem;"
                    >
                        [${index + 1}]
                    </a>
                `)}
            </div>
        `;
    };

    if (!people || people.length === 0) {
        return html`<p role="alert">No people data available for this jurisdiction.</p>`;
    }

    return html`
    <figure>
        <table role="grid">
            <thead>
                <tr>
                    <th style="width: 1%;">Photo</th>
                    <th style="width: 15%;">Official</th>
                    <th style="width: 15%;">Divisions</th>
                    <th style="width: 15%">Contact</th>
                </tr>
            </thead>
            <tbody>
                ${people.map(person => html`
                    <tr>
                        <td data-label="Photo">
                            ${person.cdn_image || person.image ? html`
                                <img 
                                    src="${person.cdn_image || person.image}" 
                                    alt="Photo of ${person.name}" 
                                    style="width: 50px; height: 50px; border-radius: 50%; object-fit: cover;"
                                    
                                    onerror="this.onerror=null; this.style.display='none'; this.closest('td').querySelector('.fallback-icon').style.display='inline-block';"
                                >
                                <span class="fallback-icon" style="display: none; width: 50px; height: 50px; line-height: 50px; text-align: center; border-radius: 50%; background: var(--pico-muted-border-color); color: var(--pico-secondary-hover-color);">👤</span>
                            ` : html`<span class="fallback-icon" style="width: 50px; height: 50px; line-height: 50px; text-align: center; border-radius: 50%; background: var(--pico-muted-border-color); color: var(--pico-secondary-hover-color); display: inline-block;">👤</span>`}
                        </td>
                        
                        <td data-label="Official">
                            <strong>${person.name}</strong>
                            <small style="display: block;">${person.roles && person.roles.join(' | ')}</small>
                        </td>

                        <td data-label="Divisions">
                            ${formatArray(person.divisions)}
                        </td>
                        
                        <td data-label="Contact">
                            ${person.email ? html`<a href="mailto:${person.email}" style="display: block;">${person.email}</a>` : ''}
                            ${person.phone_number ? html`<a href="tel:${person.phone_number}" style="display: block;">${person.phone_number}</a>` : ''}
                            ${person.website ? html`<a href="${person.website}" target="_blank" class="secondary">Link</a>` : ''}
                        </td>
                    </tr>
                `)}
            </tbody>
        </table>
    </figure>
    `;
}

customElements.define(
  "civ-people-list",
  component(PeopleList, { useShadowDOM: false, observedAttributes: [] })
);