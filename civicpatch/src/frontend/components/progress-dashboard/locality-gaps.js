import { html } from 'lit-html';
import { component, useState, useEffect } from 'haunted';
import { useAuth } from '../../hooks/useAuth.js';
import { fetchJurisdictionsByOcdids } from '../../api.js';

const PAGE_SIZE = 25;

function LocalityGaps({ stats, state }) {
  const { permissions } = useAuth();
  const [page, setPage] = useState(1);
  const [jurisdictions, setJurisdictions] = useState([]);

  if (!permissions.JURISDICTION_PAGE) return html``;
  if (!stats || !stats.states || !stats.states[state]) return html``;

  const notScraped = stats.states[state].locality_gaps.not_yet_scraped;
  if (!notScraped || notScraped.length === 0) return html``;

  const totalPages = Math.ceil(notScraped.length / PAGE_SIZE);
  const pageOcdids = notScraped.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  useEffect(() => {
    fetchJurisdictionsByOcdids(pageOcdids).then(res => setJurisdictions(res.data || []));
  }, [page, state]);

  const nameMap = Object.fromEntries(jurisdictions.map(j => [j.ocdid, j]));

  return html`
    <div>
      <small>${notScraped.length} jurisdictions</small>
      <ul>
        ${pageOcdids.map(ocdid => {
          const j = nameMap[ocdid];
          return j
            ? html`<li><a href="/jurisdictions/${j.slug}">${j.name}</a></li>`
            : html`<li>${ocdid}</li>`;
        })}
      </ul>
      ${totalPages > 1 ? html`
        <nav style="display:flex; gap:1rem; align-items:center; margin-top:1rem;">
          <button ?disabled=${page <= 1} @click=${() => setPage(p => p - 1)}>← Previous</button>
          <span>Page ${page} of ${totalPages}</span>
          <button ?disabled=${page >= totalPages} @click=${() => setPage(p => p + 1)}>Next →</button>
        </nav>
      ` : ''}
    </div>
  `;
}

customElements.define('locality-gaps', component(LocalityGaps, { useShadowDOM: false }));
export default LocalityGaps;
