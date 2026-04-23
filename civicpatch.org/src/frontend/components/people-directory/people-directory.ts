import "./people-directory.css";
import { component } from "haunted";
import { html, TemplateResult } from "lit-html";
import "../person-image.js";

interface Office {
    name: string;
    division_ocdid: string;
}

interface Person {
    id: string;
    name: string;
    office?: Office;
    emails?: string[];
    phones?: string[];
    urls?: string[];
    cdn_image?: string;
}

interface PeopleDirectoryProps {
    local: Person[];
    jurisdictionSelected: boolean;
}

function subdivisionLabel(person: Person): string | null {
    const ocdid = person.office?.division_ocdid ?? "";
    for (const part of ocdid.split("/")) {
        if (part.startsWith("council_district:")) return `District ${part.split(":")[1]}`;
        if (part.startsWith("ward:")) return `Ward ${part.split(":")[1]}`;
    }
    return null;
}

function groupPeople(people: Person[]): Map<string | null, Person[]> {
    const groups = new Map<string | null, Person[]>();
    for (const person of people) {
        const key = subdivisionLabel(person);
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key)!.push(person);
    }

    const sorted = new Map<string | null, Person[]>();
    for (const [key] of [...groups].sort(([a], [b]) => {
        if (a === null) return -1;
        if (b === null) return 1;
        const numA = parseInt(a.replace(/\D/g, ""), 10);
        const numB = parseInt(b.replace(/\D/g, ""), 10);
        return isNaN(numA) || isNaN(numB) ? a.localeCompare(b) : numA - numB;
    })) {
        sorted.set(key, groups.get(key)!);
    }
    return sorted;
}

function renderContact(person: Person): TemplateResult {
    return html`
        <div class="people-directory__contact">
            ${person.emails?.map(e => html`<a href="mailto:${e}">${e}</a>`)}
            ${person.phones?.map(p => html`<a href="tel:${p}">${p}</a>`)}
            ${person.urls?.length ? html`<a href="${person.urls[0]}" target="_blank" rel="noopener noreferrer" class="secondary">Website</a>` : ""}
        </div>
    `;
}

function renderRow(person: Person): TemplateResult {
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

function PeopleDirectory({ local = [], jurisdictionSelected = false }: PeopleDirectoryProps): TemplateResult | string {
    if (!local.length) {
        return jurisdictionSelected
            ? html`<p role="alert">No data available for this jurisdiction.</p>`
            : "";
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
    component(PeopleDirectory as any, { useShadowDOM: false, observedAttributes: [] }),
);
