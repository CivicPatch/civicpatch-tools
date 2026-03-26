import { component } from "haunted";
import { html } from "lit-html";

const FIELDS = [
  { key: "office.name",           label: "Office" },
  { key: "office.division_ocdid", label: "Division" },
  { key: "phones",                label: "Phones" },
  { key: "emails",                label: "Emails" },
  { key: "urls",                  label: "URLs" },
  { key: "start_date",            label: "Start" },
  { key: "end_date",              label: "End" },
  { key: "image",                 label: "Image" },
];

function getVal(person, key) {
  if (key === "office.name") return person?.office?.name ?? "";
  if (key === "office.division_ocdid") return person?.office?.division_ocdid ?? "";
  const v = person?.[key];
  if (Array.isArray(v)) return v.join(", ");
  return v ?? "";
}

function normalize(v) {
  return v.toLowerCase().trim();
}

function changedFields(from, to) {
  return FIELDS.filter(
    ({ key }) => normalize(getVal(from, key)) !== normalize(getVal(to, key))
  );
}

function fieldSummary(from, to, { key, label }) {
  const oldVal = getVal(from, key);
  const newVal = getVal(to, key);
  if (oldVal.length < 40 && newVal.length < 40) {
    return `${label}: ${oldVal || "—"} → ${newVal || "—"}`;
  }
  return `${label} updated`;
}

function DiffSummary({ existing, pullRequest }) {
  const existingArr = Array.isArray(existing) ? existing : [];
  const prArr = Array.isArray(pullRequest) ? pullRequest : [];
  const existingMap = Object.fromEntries(existingArr.map((p) => [p.id, p]));
  const prMap = Object.fromEntries(prArr.map((p) => [p.id, p]));
  const allKeys = Array.from(new Set([...Object.keys(existingMap), ...Object.keys(prMap)]));

  const entries = [];
  for (const key of allKeys) {
    const ex = existingMap[key];
    const pr = prMap[key];
    if (!ex) entries.push({ type: "added", person: pr });
    else if (!pr) entries.push({ type: "removed", person: ex });
    else {
      const fields = changedFields(ex, pr);
      if (fields.length) entries.push({ type: "changed", person: pr, from: ex, fields });
    }
  }

  if (!entries.length) return html``;

  return html`
    <div class="diff-summary">
      <span class="diff-summary__label">Changes since last scrape</span>
      <div class="diff-summary__cards">
        ${entries.map((e) => {
          if (e.type === "added") return html`
            <div class="diff-summary__card diff-summary__card--added">
              <span class="diff-summary__card-name"><span class="diff-summary__badge">+</span>${e.person.name || "—"}</span>
              <span class="diff-summary__card-tag">Added</span>
            </div>`;
          if (e.type === "removed") return html`
            <div class="diff-summary__card diff-summary__card--removed">
              <span class="diff-summary__card-name"><span class="diff-summary__badge">−</span>${e.person.name || "—"}</span>
              <span class="diff-summary__card-tag">Removed</span>
            </div>`;
          return html`
            <div class="diff-summary__card diff-summary__card--changed">
              <span class="diff-summary__card-name">${e.person.name || "—"}</span>
              ${e.fields.map((f) => html`
                <span class="diff-summary__field">${fieldSummary(e.from, e.person, f)}</span>
              `)}
            </div>`;
        })}
      </div>
    </div>
  `;
}

customElements.define("civ-diff-summary", component(DiffSummary, { useShadowDOM: false }));
