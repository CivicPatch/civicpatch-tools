// Bucket 1 of the officials-card audit (.scratch/wire-demo/person-cards-demo.html) — option
// 1a, the marked front-runner: a compact grid ordered by role rank instead of today's flat
// photo-row list. Read-only only — roster-section.ts still uses person-row.ts's editable
// review-row when a maintainer is editing; this is the plain "who holds this office" view.
//
// Field rows use their own text-label renderer rather than review-preview's icon-based
// renderValues(), matching the demo's plain "term ends …" / "email …" style. The underlying
// field data logic (DETAIL_FIELDS, values(), renderLink(), renderSources()) is still the real,
// shared one — only the label-vs-icon presentation differs.

import { html, nothing } from "lit-html";
import "../person-image.js";
import "./person-card-grid.css";
import { type PersonCard, personOf } from "./person-cards.js";
import { type RoleOption } from "../posts-list/posts-model.js";
import { postsHeld } from "../posts-list/posts-model.js";
import { withDisplayImage } from "../fields/field-controls.js";
import { type DiffRecord, type FieldSpec } from "../fields/field-model.js";
import { PERSON_LINK_TARGET } from "../../utils/source-links.js";
import {
  DETAIL_FIELDS,
  SOURCES_KEY,
  values,
  renderLink,
  renderSources,
  sourceMapFor,
  type SourceMap,
} from "../review-preview/preview-values.js";
import { sortByRoleRank, computeLeadIds } from "./person-card-grid-model.js";

const AVATAR_SIZE = "4rem";

function renderFieldRow(field: FieldSpec, list: string[]) {
  return html`<div class="person-card-grid__field">
    <span class="person-card-grid__field-label">${field.label}</span>
    <span class="person-card-grid__field-value">
      ${field.key === "urls"
        ? list.map((url, i) => html`${i > 0 ? ", " : ""}${renderLink(url, url, PERSON_LINK_TARGET)}`)
        : list.join(", ")}
    </span>
  </div>`;
}

function renderFields(record: DiffRecord, sources: SourceMap) {
  const populated = DETAIL_FIELDS.filter((field) => field.key !== SOURCES_KEY)
    .map((field) => [field, values(record, field)] as const)
    .filter(([, list]) => list.length > 0);
  return html`
    ${populated.map(([field, list]) => renderFieldRow(field, list))}
    ${renderSources(record, sources)}
  `;
}

function renderCard(card: PersonCard, sources: SourceMap, isLead: boolean) {
  const record = personOf(card);
  const name = record?.name || "(unnamed)";
  const office = postsHeld(record?.memberships ?? []);
  return html`
    <div class="person-card-grid__card">
      <div class="person-card-grid__body">
        <span class="person-card-grid__avatar">
          <person-image .person=${withDisplayImage(record ?? {})} .size=${AVATAR_SIZE}></person-image>
        </span>
        <div class="person-card-grid__name">${name}</div>
        ${office
          ? html`<div
              class="person-card-grid__role ${isLead ? "person-card-grid__role--lead" : ""}"
            >
              ${office}
            </div>`
          : nothing}
        <div class="person-card-grid__fields">${renderFields(record, sources)}</div>
      </div>
    </div>
  `;
}

export function renderPersonCardGrid(cards: PersonCard[], roles: RoleOption[]) {
  const roleOrder = roles.map((role) => role.id);
  const records = cards.map((card) => ({
    id: card.personId,
    memberships: personOf(card)?.memberships,
  }));
  const leadIds = computeLeadIds(records, roleOrder);
  const ordered = sortByRoleRank(
    cards.map((card) => ({ card, memberships: personOf(card)?.memberships })),
    roleOrder,
  ).map((entry) => entry.card);
  const sources = sourceMapFor(cards.map((card) => personOf(card)));

  return html`
    <div class="person-card-grid">
      ${ordered.map((card) => renderCard(card, sources, leadIds.has(card.personId)))}
    </div>
  `;
}
