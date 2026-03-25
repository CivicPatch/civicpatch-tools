import { html, component, useState, useEffect } from "haunted";
import { updatePullRequestData } from "../../api.js";
import { usePeopleState } from "../edit-people/hooks/use-people-state.js";
import { getColumns } from "../edit-people/table/columns.js";
import "../basic/table/table.js";
import "../person-image.js";

function ReviewPeopleEditor({ people, requestId, jurisdictionOcdid }) {
  const {
    currentPeople,
    dirty,
    peopleToSubmit,
    assignPeople,
    handleTableDataChange,
    handleTableDataReorder,
  } = usePeopleState({ people: people ?? [] });

  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

  useEffect(() => {
    assignPeople(people ?? []);
  }, [people]);

  const handleSubmit = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      await updatePullRequestData(requestId, jurisdictionOcdid, peopleToSubmit);
      assignPeople(peopleToSubmit);
    } catch (err) {
      setSaveError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return html`
    <div class="review-people-editor">
      <h4 class="review-people-editor__title">People</h4>
      <civ-table
        .identifier=${"id"}
        .data=${currentPeople}
        .columns=${getColumns(null)}
        .canReorder=${true}
        @data-change=${handleTableDataChange}
        @reorder=${handleTableDataReorder}
      ></civ-table>
      <div class="review-people-editor__footer">
        <button
          class="btn-sm"
          ?disabled=${!dirty || saving}
          @click=${handleSubmit}
        >${saving ? "Saving…" : "Save changes"}</button>
        ${saveError ? html`<span class="review-people-editor__error">${saveError}</span>` : ""}
      </div>
    </div>
  `;
}

customElements.define("civ-review-people-editor", component(ReviewPeopleEditor, { useShadowDOM: false }));
