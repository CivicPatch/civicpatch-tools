import { html } from 'lit-html';
import { component, useState, useEffect } from 'haunted';
import { ref } from 'lit/directives/ref.js';
import { fetchJurisdictionsByOcdids } from '../../api.js';
import { Pagination } from '../pagination/index.js';
import { jurisdictionOcdidToPath } from "../ocdid-utils.js";
import { usePagerRef } from "../../hooks/use-pager-ref.ts";

const PAGE_SIZE = 25;

function LocalityGaps({ stats, state }) {
  const [page, setPage] = useState(1);
  const [jurisdictions, setJurisdictions] = useState([]);
  const { listRef, scrollToTop } = usePagerRef();

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

  // Built once so Next/Previous re-orients to the top of the list either way — clicking
  // the bottom pager most often leaves the reader below what just changed above them.
  const pager = totalPages > 1 ? html`
    <nav style="display:flex; gap:0.5rem; align-items:center; margin-top:1rem;">
      ${Pagination({
        page,
        totalPages,
        onPrevious: () => {
          setPage(p => p - 1);
          scrollToTop();
        },
        onNext: () => {
          setPage(p => p + 1);
          scrollToTop();
        },
        onGoToPage: (n) => setPage(n),
      })}
    </nav>
  ` : '';

  return html`
    <div ${ref(listRef)}>
      <small>${notScraped.length} jurisdictions</small>
      ${pager}
      <ul>
        ${pageOcdids.map(ocdid => {
          const j = nameMap[ocdid];
          return j
            ? html`<li><a href="/${jurisdictionOcdidToPath(j.slug)}">${j.name}</a></li>`
            : html`<li>${ocdid}</li>`;
        })}
      </ul>
      ${pager}
    </div>
  `;
}

customElements.define('locality-gaps', component(LocalityGaps, { useShadowDOM: false }));
export default LocalityGaps;
