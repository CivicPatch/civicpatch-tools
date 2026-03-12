import { html } from 'lit-html';
import { component, useState } from 'haunted';
import { divisionOcdidToFriendly, jurisdictionOcdidToFriendly } from './ocdid-utils';

// ─── Styles ────────────────────────────────────────────────────────────────

const BASE_STYLES = `

  pr-card {
    display: block;
    border: 1px solid var(--pico-muted-border-color);
    border-radius: var(--pico-border-radius);
    overflow: hidden;
  }

  .pr-card__header {
    display: flex;
    align-items: baseline;
    gap: 0.6rem;
    padding: 0.75rem 1rem 0.6rem;
    border-bottom: 1px solid var(--pico-muted-border-color);
    flex-wrap: wrap;
  }

  .pr-card__jurisdiction {
    font-family: var(--pico-font-family-monospace);
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--pico-primary-inverse);
    background: var(--pico-primary-background);
    border: 1px solid var(--pico-primary-border);
    padding: 0.15em 0.55em;
    border-radius: calc(var(--pico-border-radius) * 0.5);
    white-space: nowrap;
  }

  .pr-card__title {
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--pico-color);
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .pr-card__link {
    font-family: var(--pico-font-family-monospace);
    font-size: 0.75rem;
    color: var(--pico-primary);
    text-decoration: none;
    white-space: nowrap;
  }
  .pr-card__link:hover {
    text-decoration: underline;
  }

  .pr-card__state {
    font-family: var(--pico-font-family-monospace);
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    padding: 0.2em 0.6em;
    border-radius: 20px;
    white-space: nowrap;
    border: 1px solid var(--pico-muted-border-color);
    color: var(--pico-muted-color);
  }
  .pr-card__state--open   { color: var(--pico-ins-color); border-color: var(--pico-ins-color); }
  .pr-card__state--closed { color: var(--pico-del-color); border-color: var(--pico-del-color); }
  .pr-card__state--merged { color: var(--pico-primary);   border-color: var(--pico-primary);   }

  .pr-card__meta {
    padding: 0.3rem 1rem 0.5rem;
    font-family: var(--pico-font-family-monospace);
    font-size: 0.7rem;
    color: var(--pico-muted-color);
    border-bottom: 1px solid var(--pico-muted-border-color);
    letter-spacing: 0.02em;
  }

  /* ── Diff panel ── */

  .diff-panel {
    padding: 0.75rem 1rem 1rem;
  }

  .diff-panel__toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.6rem;
  }

  .diff-panel__summary {
    font-family: var(--pico-font-family-monospace);
    font-size: 0.7rem;
    color: var(--pico-muted-color);
    letter-spacing: 0.03em;
  }

  .diff-panel__toggle {
    font-family: var(--pico-font-family-monospace);
    font-size: 0.68rem;
    background: transparent;
    border: 1px solid var(--pico-muted-border-color);
    color: var(--pico-muted-color);
    padding: 0.25em 0.75em;
    border-radius: var(--pico-border-radius);
    cursor: pointer;
    letter-spacing: 0.04em;
    transition: border-color 0.15s, color 0.15s;
  }
  .diff-panel__toggle:hover {
    border-color: var(--pico-color);
    color: var(--pico-color);
  }

  .diff-panel__empty {
    font-family: var(--pico-font-family-monospace);
    font-size: 0.75rem;
    color: var(--pico-muted-color);
    padding: 1rem 0;
    text-align: center;
    letter-spacing: 0.03em;
  }

  /* ── Table ── */

  .diff-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.73rem;
    table-layout: fixed;
  }

  .diff-table th {
    text-align: left;
    font-size: 0.62rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--pico-muted-color);
    padding: 0.3rem 0.5rem 0.4rem;
    border-bottom: 1px solid var(--pico-muted-border-color);
  }

  .diff-table td {
    padding: 0.28rem 0.5rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    vertical-align: middle;
    color: var(--pico-muted-color);
    border-bottom: 1px solid var(--pico-muted-border-color);
  }

  .diff-table tbody tr:last-child td {
    border-bottom: none;
  }

  .diff-table td:first-child {
    color: var(--pico-color);
    padding-left: 0.85rem;
  }

  .row--added   td { background: var(--pico-ins-background); }
  .row--removed td { background: var(--pico-del-background); }
  .row--unchanged  { opacity: 0.5; }
  td.cell--changed { background: var(--pico-info-background); }

  ins { text-decoration: none; color: var(--pico-color); }
  del { text-decoration: line-through; color: var(--pico-color); text-decoration-color: var(--pico-del-color); }

  .diff-table .col-name   { width: 22%; }
  .diff-table .col-before { width: 26%; }
  .diff-table .col-after  { width: 26%; }
  .diff-table .col-div    { width: 16%; }
  .diff-table .col-src    { width: 10%; }

  .source-link {
    font-size: 0.65rem;
    color: var(--pico-primary);
    text-decoration: none;
    margin-right: 0.3em;
    opacity: 0.75;
  }
  .source-link:hover { opacity: 1; }
`;

if (!document.getElementById('pr-card-styles')) {
  const style = document.createElement('style');
  style.id = 'pr-card-styles';
  style.textContent = BASE_STYLES;
  document.head.appendChild(style);
}

// ─── Utilities ─────────────────────────────────────────────────────────────

export function stateColor(state) {
  switch (state) {
    case "open":   return "open";
    case "closed": return "closed";
    case "merged": return "merged";
    default:       return "draft";
  }
}

const getPrNumberFromUrl = url => {
  try { return url.split('/').pop(); } catch { return ""; }
};

// ─── Sub-components ────────────────────────────────────────────────────────

const PrHeader = ({ pr }) => html`
  <div class="pr-card__header">
    <span class="pr-card__jurisdiction">
      ${jurisdictionOcdidToFriendly(pr?.jurisdiction_ocdid)}
    </span>
    ${pr?.github_title
      ? html`<span class="pr-card__title">${pr.github_title}</span>`
      : ''}
    <a class="pr-card__link" href=${pr?.url} target="_blank" rel="noopener">
      #${getPrNumberFromUrl(pr?.url) || '—'}
    </a>
    <span class="pr-card__state pr-card__state--${stateColor(pr?.github_state)}">
      ${pr?.github_state || 'unknown'}
    </span>
    <a class="pr-card__link" href="/jurisdictions?jurisdiction_ocdid=${pr?.jurisdiction_ocdid}" target="_blank" rel="noopener">
      Detail
    </a>
  </div>
`;

const PrTimestamp = ({ createdAt }) =>
  createdAt
    ? html`<div class="pr-card__meta">
        created ${new Date(createdAt).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })}
      </div>`
    : '';

// ─── Row renderer ──────────────────────────────────────────────────────────

function renderRow({ row, type }) {
  const name       = row.person.name;
  const beforeRole = row.from?.office?.name || row.person.office?.name || '—';
  const afterRole  = row.person.office?.name || '—';
  const beforeDiv  = divisionOcdidToFriendly(row.from?.office?.division_ocdid) || '—';
  const afterDiv   = divisionOcdidToFriendly(row.person.office?.division_ocdid) || '—';

  const sourceUrls = Array.from(new Set([
    ...(row.person?.source_urls || []),
    ...(row.from?.source_urls   || []),
  ]));

  const urlLinks = sourceUrls.map((url, i) =>
    html`<a class="source-link" href=${url} target="_blank" rel="noopener">[${i}]</a>`
  );

  if (type === 'added') return html`
    <tr class="row--added">
      <td><ins>${name}</ins></td>
      <td></td>
      <td><ins>${afterRole}</ins></td>
      <td><ins>${afterDiv}</ins></td>
      <td>${urlLinks}</td>
    </tr>`;

  if (type === 'removed') return html`
    <tr class="row--removed">
      <td><del>${name}</del></td>
      <td><del>${beforeRole}</del></td>
      <td></td>
      <td><del>${beforeDiv}</del></td>
      <td>${urlLinks}</td>
    </tr>`;

  if (type === 'changed') {
    const roleChanged = beforeRole !== afterRole;
    const divChanged  = beforeDiv  !== afterDiv;
    return html`
    <tr class="row--changed">
      <td>${name}</td>
      <td class="${roleChanged ? 'cell--changed' : ''}"><del>${beforeRole}</del></td>
      <td class="${roleChanged ? 'cell--changed' : ''}"><ins>${afterRole}</ins></td>
      <td class="${divChanged  ? 'cell--changed' : ''}">${divChanged ? html`<del>${beforeDiv}</del> <ins>${afterDiv}</ins>` : afterDiv}</td>
      <td>${urlLinks}</td>
    </tr>`;
  }

  if (type === 'unchanged') return html`
    <tr class="row--unchanged">
      <td>${name}</td>
      <td>${beforeRole}</td>
      <td>${afterRole}</td>
      <td>${afterDiv}</td>
      <td>${urlLinks}</td>
    </tr>`;

  return null;
}

// ─── DataPanel ─────────────────────────────────────────────────────────────

const DataPanel = ({ data }) => {
  const [showUnchanged, setShowUnchanged] = useState(false);

  const getKey = person => person?.id;
  const existingData = Array.isArray(data?.existing)     ? data.existing     : [];
  const prData       = Array.isArray(data?.pull_request) ? data.pull_request : [];
  const existingMap  = Object.fromEntries(existingData.map(p => [getKey(p), p]));
  const prMap        = Object.fromEntries(prData.map(p => [getKey(p), p]));
  const allKeys      = Array.from(new Set([...Object.keys(existingMap), ...Object.keys(prMap)]));

  const diffRows      = [];
  const unchangedRows = [];

  for (const key of allKeys) {
    const existing = existingMap[key];
    const pr       = prMap[key];
    if (existing && !pr) {
      diffRows.push({ type: 'removed', person: existing, from: existing });
    } else if (!existing && pr) {
      diffRows.push({ type: 'added', person: pr, from: pr });
    } else if (existing && pr) {
      const changed =
        (existing.office?.name           || '') !== (pr.office?.name           || '') ||
        (existing.office?.division_ocdid || '') !== (pr.office?.division_ocdid || '');
      if (changed) {
        diffRows.push({ type: 'changed', person: pr, from: existing });
      } else {
        unchangedRows.push({ type: 'unchanged', person: pr, from: existing });
      }
    }
  }

  if (diffRows.length === 0 && unchangedRows.length === 0) {
    return html`<div class="diff-panel"><p class="diff-panel__empty">No data.</p></div>`;
  }

  if (diffRows.length === 0 && !showUnchanged) {
    return html`
      <div class="diff-panel">
        <div class="diff-panel__toolbar">
          <span class="diff-panel__summary">No changes detected.</span>
          <button class="diff-panel__toggle" @click=${() => setShowUnchanged(true)}>
            Show ${unchangedRows.length} unchanged
          </button>
        </div>
      </div>`;
  }

  const added   = diffRows.filter(r => r.type === 'added').length;
  const removed = diffRows.filter(r => r.type === 'removed').length;
  const changed = diffRows.filter(r => r.type === 'changed').length;
  const summaryParts = [
    added   && `+${added}`,
    removed && `−${removed}`,
    changed && `~${changed}`,
  ].filter(Boolean).join('  ');

  return html`
    <div class="diff-panel">
      <div class="diff-panel__toolbar">
        <span class="diff-panel__summary">${summaryParts}</span>
        ${unchangedRows.length > 0 ? html`
          <button class="diff-panel__toggle" @click=${() => setShowUnchanged(!showUnchanged)}>
            ${showUnchanged ? 'Hide' : `Show ${unchangedRows.length}`} unchanged
          </button>` : ''}
      </div>
      <table class="diff-table">
        <colgroup>
          <col class="col-name">
          <col class="col-before">
          <col class="col-after">
          <col class="col-div">
          <col class="col-src">
        </colgroup>
        <thead>
          <tr>
            <th>Name</th>
            <th>Before</th>
            <th>After</th>
            <th>Division</th>
            <th>Src</th>
          </tr>
        </thead>
        <tbody>
          ${diffRows.map(row => renderRow({ row, type: row.type }))}
          ${showUnchanged ? unchangedRows.map(row => renderRow({ row, type: row.type })) : ''}
        </tbody>
      </table>
    </div>
  `;
};

// ─── PrCard ────────────────────────────────────────────────────────────────

function PrCard({ pr, data }) {
  return html`
    <div class="pr-card">
      ${PrHeader({ pr })}
      ${PrTimestamp({ createdAt: pr?.created_at })}
      ${DataPanel({ data })}
    </div>
  `;
}

customElements.define('pr-card', component(PrCard, { useShadowDOM: false }));