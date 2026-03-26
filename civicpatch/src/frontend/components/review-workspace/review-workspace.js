import { html, component, useEffect } from "haunted";
import { usePeopleState } from "../edit-people/hooks/use-people-state.js";
import { getColumns } from "../edit-people/table/columns.js";
import "../basic/table/table.js";
import "../person-image.js";

function ReviewWorkspace({ pullRequest, existing }) {
  const pullRequestArr = Array.isArray(pullRequest) ? pullRequest : [];
  const existingArr = Array.isArray(existing) ? existing : [];

  const {
    currentPeople,
    dirty,
    peopleToSubmit,
    assignPeople,
    handleTableDataChange,
    handleTableDataReorder,
  } = usePeopleState({ people: pullRequestArr });

  useEffect(() => {
    assignPeople(pullRequestArr);
  }, [pullRequest]);

  useEffect(() => {
    this.dispatchEvent(new CustomEvent("dirty-change", {
      bubbles: true,
      detail: { dirty, people: peopleToSubmit },
    }));
  }, [dirty, peopleToSubmit]);

  const existingIds = new Set(existingArr.map((p) => p.id));
  const matchedPeople = currentPeople.filter((p) => existingIds.has(p.id));
  const newPeople = currentPeople.filter((p) => !existingIds.has(p.id));
  const allEditable = [...matchedPeople, ...newPeople];

  const columns = getColumns(null);

  return html`
    <div class="review-workspace">
      ${allEditable.length ? html`
        <civ-table
          .identifier=${"id"}
          .data=${allEditable}
          .columns=${columns}
          .canReorder=${true}
          @data-change=${handleTableDataChange}
          @reorder=${handleTableDataReorder}
        ></civ-table>
      ` : ""}
    </div>
  `;
}

customElements.define("civ-review-workspace", component(ReviewWorkspace, { useShadowDOM: false }));
