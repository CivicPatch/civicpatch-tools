import { component } from "haunted";
import { html } from "lit-html";
import "./basic/table/table.js";
import "./person-image.js";
import {
import { postsHeld } from "./posts-list/posts-model.js";
  DIVISION_COUNCIL_DISTRICT,
  DIVISION_WARD,
} from "./edit-people/person-edit-utils.ts";

function PeopleList({ local = [], jurisdictionSelected = false }) {
  const people = local;

  const hasSubdivision = (person) => {
    const divisionOcdid = person.office?.division_ocdid || "";
    return divisionOcdid.includes("district") || divisionOcdid.includes("ward");
  };

  const getSubdivisionLabel = (person) => {
    const divisionOcdid = person.office?.division_ocdid || "";
    for (const part of divisionOcdid.split("/")) {
      if (part.startsWith(`${DIVISION_COUNCIL_DISTRICT}:`)) return `District ${part.split(":")[1]}`;
      if (part.startsWith(`${DIVISION_WARD}:`)) return `Ward ${part.split(":")[1]}`;
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
        <small style="display: block;">${postsHeld(person.memberships ?? [])}</small>
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
    return jurisdictionSelected
      ? html`<p role="alert">No data available for this jurisdiction.</p>`
      : html``;
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
