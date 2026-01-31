import { component } from "haunted";
import { html } from "lit-html";

function PeopleList({ local = [] }) {
    const people = local;

    const hasSubdivision = (person) => {
        const divisionOcdid = person.office.division_ocdid || "";
        if (divisionOcdid.includes("district") || divisionOcdid.includes("ward")) {
            return true;
        }
        return false;
    }

    const getSubdivisionLabel = (person) => {
        const divisionOcdid = person.office.division_ocdid || "";
        const parts = divisionOcdid.split("/");
        for (const part of parts) {
            if (part.startsWith("council_district:")) {
                return `District ${part.split(":")[1]}`;
            } else if (part.startsWith("ward:")) {
                return `Ward ${part.split(":")[1]}`;
            }
        }
    }
    

    const subDivision = (person) => {
        if (hasSubdivision(person)) {
            return `${getSubdivisionLabel(person)}`;
        }
        return null;
    }

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
                            <small style="display: block;">${person.office && person.office.name}</small>
                            <small style="display: block;">${subDivision(person)}</small>
                        </td>

                        <td data-label="Contact">
                            ${person.emails ? html`<a href="mailto:${person.emails.join(',')}" style="display: block;">${person.emails.join(',')}</a>` : ''}
                            ${person.phones ? html`<a href="tel:${person.phones.join(',')}" style="display: block;">${person.phones.join(',')}</a>` : ''}
                            ${person.urls ? html`<a href="${person.urls.join(',')}" target="_blank" class="secondary">Link</a>` : ''}
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