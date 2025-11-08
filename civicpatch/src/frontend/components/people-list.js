import { component } from "haunted";
import { html } from "lit-html";

function PeopleList({ peopleData = [] }) {
    // Dummy data in case peopleData is not passed or is empty
    const dummyPeople = peopleData.length > 0 ? peopleData : [
        {
            phone_number: "(555) 123-4567",
            email: "alice@example.gov",
            roles: ["Mayor", "Council Member"],
            divisions: ["Executive", "Local Government"],
            website: "https://alice.gov",
            sources: ["Official Bio", "LinkedIn"],
            photo: "https://picsum.photos/id/1005/50/50"
        },
        {
            phone_number: "(555) 987-6543",
            email: "bob@example.org",
            roles: ["Treasurer"],
            divisions: ["Finance"],
            website: "https://bob.org",
            sources: ["Campaign Site"],
            photo: "https://picsum.photos/id/1025/50/50"
        }
    ];

    return html`
    <figure>
        <table role="grid">
            <thead>
                <tr>
                    <th></th>
                    <th>Name / Role</th>
                    <th>Divisions</th>
                    <th>Contact</th>
                    <th>Website</th>
                    <th>Sources</th>
                </tr>
            </thead>
            <tbody>
                ${dummyPeople.map(person => html`
                    <tr>
                        <td data-label="Photo">
                            <img src="${person.photo}" alt="Photo of ${person.email}" style="width: 50px; height: 50px; border-radius: 50%;">
                        </td>
                        
                        <td data-label="Name / Role">
                            <strong>${person.email}</strong>
                            <small>(${person.roles.join(', ')})</small>
                        </td>
                        
                        <td data-label="Divisions">
                            ${person.divisions.map(div => html`<span style="display: block;">${div}</span>`)}
                        </td>
                        
                        <td data-label="Contact">
                            <a href="tel:${person.phone_number}">${person.phone_number}</a>
                        </td>
                        
                        <td data-label="Website">
                            <a href="${person.website}" target="_blank">View Site</a>
                        </td>
                        
                        <td data-label="Sources">
                            ${person.sources.map(source => html`<span style="display: block; font-size: 0.8rem;">${source}</span>`)}
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