import { html } from 'lit-html';
import { component, useEffect, useState } from 'haunted';
import { fetchDashboard, fetchMunicipalityList } from '../../api.js';
import { dateStringToFriendly } from '../../utils/date-utils.js';
import { jurisdictionOcdidToPath } from '../../components/ocdid-utils.js';
import './municipalities-page.css';

interface MunicipalitiesPageProps {
  state?: string;
}

interface Municipality {
  jurisdiction_ocdid: string;
  name: string;
  status: string;
  needs_review: boolean;
  officials_count: number;
  last_verified_at: string | null;
}

function MunicipalitiesPage({ state = '' }: MunicipalitiesPageProps) {
  const [municipalities, setMunicipalities] = useState<Municipality[] | null>(null);
  const [cutoff, setCutoff] = useState<string | null>(null);

  // One-shot per-state fetch (§8) — client-side search/filter/sort/pagination
  // (Commits 9–10) all operate on this same in-memory list, no per-interaction
  // network round-trip.
  useEffect(() => {
    if (!state) return;
    fetchMunicipalityList(state)
      .then((d) => setMunicipalities(d.data ?? []))
      .catch(() => setMunicipalities([]));
    fetchDashboard()
      .then((d) => setCutoff(d.data?.states?.[state]?.civicpatch?.cutoff ?? null))
      .catch(() => {});
  }, [state]);

  const stateLabel = state.toUpperCase();

  return html`
    <div class="municipalities-page">
      <div class="municipalities-page__header">
        <a class="municipalities-page__breadcrumb" href="/">← Map</a>
        <span class="municipalities-page__breadcrumb-sep">/</span>
        <span class="municipalities-page__breadcrumb">${stateLabel}</span>
        <span class="municipalities-page__breadcrumb-sep">/</span>
        <span class="municipalities-page__breadcrumb">Local</span>
      </div>
      <div class="municipalities-page__title-row">
        <div>
          <p class="municipalities-page__eyebrow">CIVIC DATA — ${stateLabel}</p>
          <h1 class="municipalities-page__h1">${stateLabel} municipalities</h1>
        </div>
        ${cutoff
          ? html`<p class="municipalities-page__cutoff">
              Data fresh after ${dateStringToFriendly(cutoff)}
            </p>`
          : ''}
      </div>
      <hr class="municipalities-page__hairline" />

      ${municipalities === null
        ? html`<p>Loading…</p>`
        : html`
            <p class="municipalities-page__count">
              ${municipalities.length} municipalities
            </p>
            <ul class="municipalities-page__list">
              ${municipalities.map(
                (m) => html`<li>
                  <a href="/${jurisdictionOcdidToPath(m.jurisdiction_ocdid)}">${m.name}</a>
                </li>`,
              )}
            </ul>
          `}
    </div>
  `;
}

customElements.define(
  'municipalities-page',
  component(MunicipalitiesPage as any, {
    useShadowDOM: false,
    observedAttributes: ['state'],
  }),
);
