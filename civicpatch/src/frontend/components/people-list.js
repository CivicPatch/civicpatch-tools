import { component } from "haunted";
import { html } from "lit-html";
import "./basic/table/table.js";
import "./person-image.js";

function PeopleList({ local = [] }) {
  const people = local;

  const hasSubdivision = (person) => {
    const divisionOcdid = person.office?.division_ocdid || "";
    return divisionOcdid.includes("district") || divisionOcdid.includes("ward");
  };

  const getSubdivisionLabel = (person) => {
    const divisionOcdid = person.office?.division_ocdid || "";
    for (const part of divisionOcdid.split("/")) {
      if (part.startsWith("council_district:")) return `District ${part.split(":")[1]}`;
      if (part.startsWith("ward:")) return `Ward ${part.split(":")[1]}`;
    }
  };

  const columns = [
    {
      label: "Photo",
      field: "photo",
      renderCell: (person) => html`<person-image .person=${person}></person-image>`,
    },
    {
      label: "Official",
      field: "official",
      renderCell: (person) => html`
        <strong>${person.name}</strong>
        <small style="display: block;">${person.office?.name}</small>
        ${hasSubdivision(person) ? html`<small style="display: block;">${getSubdivisionLabel(person)}</small>` : ""}
      `,
    },
    {
      label: "Contact",
      field: "contact",
      renderCell: (person) => html`
        ${person.emails?.length > 0 ? html`<a href="mailto:${person.emails.join(",")}" style="display: block;">${person.emails.join(",")}</a>` : ""}
        ${person.phones?.length > 0 ? html`<a href="tel:${person.phones.join(",")}" style="display: block;">${person.phones.join(",")}</a>` : ""}
        ${person.urls?.length > 0 ? html`<a href="${person.urls[0]}" target="_blank" class="secondary">Link</a>` : ""}
      `,
    },
  ];

  if (!people || people.length === 0) {
    return html`<p role="alert">No data available for this jurisdiction.</p>`;
  }

  return html`
    <civ-table
      .columns=${columns}
      .data=${people}
      .identifier=${"id"}
    ></civ-table>
  `;
}

customElements.define(
  "civ-people-list",
  component(PeopleList, { useShadowDOM: false, observedAttributes: [] }),
);
