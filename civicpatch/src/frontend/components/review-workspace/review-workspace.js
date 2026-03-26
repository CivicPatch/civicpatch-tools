import { html, component, useState, useEffect } from "haunted";
import { updatePullRequestData } from "../../api.js";
import { usePeopleState } from "../edit-people/hooks/use-people-state.js";
import { getColumns } from "../edit-people/table/columns.js";
import "../basic/table/table.js";
import "../person-image.js";

function ReviewWorkspace({ pullRequest, existing, requestId, jurisdictionOcdid }) {
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

  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

  useEffect(() => {
    assignPeople(pullRequestArr);
  }, [pullRequest]);

  const existingIds = new Set(existingArr.map((p) => p.id));
  const prIds = new Set(pullRequestArr.map((p) => p.id));

  const matchedPeople = currentPeople.filter((p) => existingIds.has(p.id));
  const newPeople = currentPeople.filter((p) => !existingIds.has(p.id));
  const allEditable = [...matchedPeople, ...newPeople];
  const missingPeople = existingArr.filter((p) => !prIds.has(p.id));

  const columns = getColumns(null);

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

  const renderTable = (people, opts = {}) => html`
    <civ-table
      .identifier=${"id"}
      .data=${people}
      .columns=${columns}
      .canReorder=${opts.canReorder ?? false}
      @data-change=${handleTableDataChange}
      @reorder=${handleTableDataReorder}
    ></civ-table>
  `;

  return html`
    <div class="review-workspace">
      ${allEditable.length ? renderTable(allEditable, { canReorder: true }) : ""}

      ${missingPeople.length ? html`
        <div class="review-workspace__section-header review-workspace__section-header--missing">
          <span class="review-workspace__section-icon">?</span>
          Missing — in database, not in scrape
        </div>
        <civ-table
          .identifier=${"id"}
          .data=${missingPeople}
          .columns=${columns}
          .canReorder=${false}
        ></civ-table>
      ` : ""}

      <div class="review-workspace__footer">
        <button
          class="btn-sm"
          ?disabled=${!dirty || saving}
          @click=${handleSubmit}
        >${saving ? "Saving…" : "Save changes"}</button>
        ${saveError ? html`<span class="review-workspace__error">${saveError}</span>` : ""}
      </div>
    </div>
  `;
}

customElements.define("civ-review-workspace", component(ReviewWorkspace, { useShadowDOM: false }));
