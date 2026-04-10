import { html } from 'lit-html';
import { component, useState, useEffect } from 'haunted';
import { useAuth } from '../../hooks/useAuth.js';
import { fetchJurisdictionsByOcdids } from '../../api.js';
import { Pagination } from '../pagination/index.js';

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
    setJurisdictions([]);
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
            ? html`<li><a href="/${j.slug}">${j.name}</a></li>`
            : html`<li>${ocdid}</li>`;
        })}
      </ul>
      ${totalPages > 1 ? html`
        <nav style="display:flex; gap:0.5rem; align-items:center; margin-top:1rem;">
          ${Pagination({
            page,
            totalPages,
            onPrevious: () => setPage(p => p - 1),
            onNext: () => setPage(p => p + 1),
            onGoToPage: (n) => setPage(n),
          })}
        </nav>
      ` : ''}
    </div>
  `;
}

customElements.define('locality-gaps', component(LocalityGaps, { useShadowDOM: false }));
export default LocalityGaps;
