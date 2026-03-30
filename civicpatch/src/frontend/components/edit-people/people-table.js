import { html, component } from "haunted";
import "../basic/table/table.js";

function PeopleTable({ data, columns }) {
  if (!data?.length) return html``;
  return html`
    <civ-table
      .identifier=${"id"}
      .canReorder=${true}
      .data=${data}
      .columns=${columns}
    ></civ-table>
  `;
}

customElements.define("civ-people-table", component(PeopleTable, { useShadowDOM: false }));
