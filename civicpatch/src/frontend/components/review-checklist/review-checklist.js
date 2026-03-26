import { html, component, useState, useEffect } from "haunted";

function ReviewChecklist({ reviewData }) {
  const [checked, setChecked] = useState(new Set());

  useEffect(() => {
    setChecked(new Set());
  }, [reviewData]);

  if (!reviewData) return html``;

  const toggle = (i) => {
    const next = new Set(checked);
    next.has(i) ? next.delete(i) : next.add(i);
    setChecked(next);
  };

  const renderCheckmark = (value) =>
    value
      ? html`<i class="fa-solid fa-check" style="color: var(--pico-ins-color);"></i>`
      : html`<i class="fa-solid fa-xmark" style="color: var(--pico-del-color);"></i>`;

  return html`
    <div class="review-checklist">
      ${reviewData.issues?.length ? html`
        <div class="review-checklist__issues">
          <h4 class="review-checklist__section-title">Issues</h4>
          <ul class="review-checklist__list">
            ${reviewData.issues.map((issue, i) => html`
              <li class="review-checklist__item ${checked.has(i) ? "review-checklist__item--checked" : ""}">
                <label class="review-checklist__label">
                  <input
                    type="checkbox"
                    class="review-checklist__checkbox"
                    .checked=${checked.has(i)}
                    @change=${() => toggle(i)}
                  />
                  ${issue}
                </label>
              </li>
            `)}
          </ul>
        </div>
      ` : ""}

      ${reviewData.people_by_source?.length ? html`
        <div class="review-checklist__people">
          <h4 class="review-checklist__section-title">People by Source</h4>
          <table role="grid">
            <thead>
              <tr>
                <th>Name</th>
                <th style="text-align: center;">Research</th>
                <th style="text-align: center;">Data</th>
              </tr>
            </thead>
            <tbody>
              ${reviewData.people_by_source.map(row => html`
                <tr>
                  <td>${row.name}</td>
                  <td style="text-align: center;">${renderCheckmark(row.in_research)}</td>
                  <td style="text-align: center;">${renderCheckmark(row.in_data)}</td>
                </tr>
              `)}
            </tbody>
          </table>
        </div>
      ` : ""}
    </div>
  `;
}

customElements.define("civ-review-checklist", component(ReviewChecklist, { useShadowDOM: false }));
