import "./people-directory.css";
import { component } from "haunted";
import { html } from "lit-html";
import "../person-image.js";

function subdivisionLabel(person) {
    const ocdid = person.office?.division_ocdid || "";
    for (const part of ocdid.split("/")) {
        if (part.startsWith("council_district:")) return `District ${part.split(":")[1]}`;
        if (part.startsWith("ward:")) return `Ward ${part.split(":")[1]}`;
    }
    return null;
}

function groupPeople(people) {
    const groups = new Map();
    for (const person of people) {
        const key = subdivisionLabel(person);
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key).push(person);
    }

    const sorted = new Map();
    if (groups.has(null)) sorted.set(null, groups.get(null));
    for (const [key] of [...groups].sort(([a], [b]) => {
        if (a === null) return -1;
        if (b === null) return 1;
        const numA = parseInt(a.replace(/\D/g, ""), 10);
        const numB = parseInt(b.replace(/\D/g, ""), 10);
        return isNaN(numA) || isNaN(numB) ? a.localeCompare(b) : numA - numB;
    })) {
        sorted.set(key, groups.get(key));
    }
    return sorted;
}

function renderContact(person) {
    return html`
        <div class="people-directory__contact">
            ${person.emails?.map(e => html`<a href="mailto:${e}">${e}</a>`)}
            ${person.phones?.map(p => html`<a href="tel:${p}">${p}</a>`)}
            ${person.urls?.length > 0 ? html`<a href="${person.urls[0]}" target="_blank" rel="noopener noreferrer" class="secondary">Website</a>` : ""}
        </div>
    `;
}

function renderRow(person) {
    return html`
        <div class="people-directory__row">
            <person-image .person=${person}></person-image>
            <div class="people-directory__info">
                <p class="people-directory__name">${person.name}</p>
                <p class="people-directory__office">${person.office?.name ?? ""}</p>
                ${renderContact(person)}
            </div>
        </div>
    `;
}

function PeopleDirectory({ local = [], jurisdictionSelected = false }) {
    if (!local.length) {
        return jurisdictionSelected
            ? html`<p role="alert">No data available for this jurisdiction.</p>`
            : html``;
    }

    const groups = groupPeople(local);
    const hasSubdivisions = groups.size > 1 || !groups.has(null);

    return html`
        <div class="people-directory">
            ${[...groups].map(([label, people]) => html`
                <div>
                    ${hasSubdivisions ? html`
                        <h5 class="people-directory__group-label">${label ?? "At Large"}</h5>
                    ` : ""}
                    ${people.map(renderRow)}
                </div>
            `)}
        </div>
    `;
}

customElements.define(
    "civ-people-directory",
    component(PeopleDirectory, { useShadowDOM: false, observedAttributes: [] }),
);
