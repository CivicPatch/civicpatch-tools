import "./jurisdiction-modal.css";
import { component, useEffect, useState } from "haunted";
import { html } from "lit-html";
import { fetchJurisdiction, fetchPeople } from "../../api.js";
import {
  jurisdictionOcdidToFriendly,
  jurisdictionOcdidToPath,
} from "../ocdid-utils.js";
import "../basic/modal.js";
import "../people/person-row.css";
import "../person-editor/person-editor.css";
import { dateStringToFriendly } from "../../utils/date-utils.js";
import "../review-preview/review-preview.css";
import { renderPersonRow } from "../people/person-row.js";
import {
  renderValues,
  sourceMapFor,
} from "../review-preview/preview-values.js";
import "../jurisdiction-search/jurisdiction-search.ts";
import { postsHeld } from "../posts-list/posts-model.js";
import type { PersonMembership } from "../edit-people/person-edit-utils.js";

const CLOSE_EVENT = "close-jurisdiction";

interface Official {
  name?: string;
  memberships?: PersonMembership[];
}

// Mirrors renderOfficialsCards on the jurisdiction page: same row renderer, same
// source map, same .review-preview__grid container. The rows are laid out by that
// container, and sourceMapFor builds the source links renderValues reads — using the
// renderer without both leaves rows unstyled and sourceless.
const renderOfficials = (people: Official[]) => {
  const sources = sourceMapFor(people as never[]);
  return html`
    <div class="review-preview__grid">
      ${people.map((person) => {
        // Post label, then membership label. `office.name` joined every source label with
        // " - " and a division badge repeated the district, so one post read three times.
        const office = postsHeld(person.memberships ?? []);
        return renderPersonRow({
          record: person as never,
          name: person.name || "(unnamed)",
          subtitle: office,
          meta: renderValues(person as never, sources),
        });
      })}
    </div>
  `;
};

interface JurisdictionData {
  url?: string;
  wiki_url?: string;
  population?: number;
  geoid?: string;
}

// Same field/label/control markup the jurisdiction page uses for its read-only rows, so
// the two read alike; only rows with a value are shown, since a modal has no room for
// empty ones.
const renderDetail = (label: string, value: unknown, href?: string) => {
  if (value === null || value === undefined || value === "") return "";
  return html`
    <div class="person-editor__field">
      <div class="person-editor__label">${label}</div>
      <div class="person-editor__control">
        ${href
          ? html`<a href=${href} target="_blank" rel="noopener noreferrer"
              >${value}</a
            >`
          : value}
      </div>
    </div>
  `;
};

const renderDetails = (
  data: JurisdictionData,
  scrapedAt: string | null,
) => html`
  <div class="jurisdiction-modal__details">
    ${renderDetail("Website", data.url, data.url)}
    ${renderDetail("Wikipedia", data.wiki_url, data.wiki_url)}
    ${renderDetail("Population", data.population?.toLocaleString?.())}
    ${renderDetail("GEOID", data.geoid)}
    ${renderDetail(
      "Last scraped",
      scrapedAt ? dateStringToFriendly(scrapedAt) : "Never",
    )}
  </div>
`;

interface Props {
  jurisdictionOcdid: string;
  displayName: string;
  parentNames: string[];
}

function JurisdictionModal(
  this: HTMLElement,
  { jurisdictionOcdid, displayName, parentNames }: Props,
) {
  // null means "not loaded yet". A separate loading flag needs both variables kept in
  // step, and any path that forgets one leaves the modal stuck on its spinner.
  const [people, setPeople] = useState<Official[] | null>(null);
  const [details, setDetails] = useState<{
    data: JurisdictionData;
    scraped_at: string | null;
  } | null>(null);

  useEffect(() => {
    if (!jurisdictionOcdid) return;
    setPeople(null);

    // Re-searching inside the modal switches jurisdictions mid-flight; without this a
    // slow response for the old one can land after the new one.
    let cancelled = false;
    fetchPeople(jurisdictionOcdid)
      .then((body) => {
        if (!cancelled) setPeople(body.data ?? []);
      })
      .catch(() => {
        if (!cancelled) setPeople([]);
      });
    return () => {
      cancelled = true;
    };
  }, [jurisdictionOcdid]);

  useEffect(() => {
    if (!jurisdictionOcdid) return;
    setDetails(null);
    let cancelled = false;
    fetchJurisdiction(jurisdictionOcdid)
      .then((body) => {
        if (!cancelled) setDetails(body);
      })
      .catch(() => {
        if (!cancelled) setDetails(null);
      });
    return () => {
      cancelled = true;
    };
  }, [jurisdictionOcdid]);

  const handleClose = () =>
    this.dispatchEvent(
      new CustomEvent(CLOSE_EVENT, { bubbles: true, composed: true }),
    );

  const title = displayName || jurisdictionOcdidToFriendly(jurisdictionOcdid);
  const where = parentNames?.length ? parentNames.join(", ") : "";

  const content = html`
    <div class="jurisdiction-modal">
      <!-- Search stays available inside, so a wrong pick is one keystroke from a
           correction rather than a close-and-retry. -->
      <civ-jurisdiction-search></civ-jurisdiction-search>

      <div class="jurisdiction-modal__body">
        <!-- Officials take the wider column: they are what the reader came for, and
             they are the only part whose length varies. -->
        <div class="jurisdiction-modal__officials" tabindex="0">
          ${people === null
            ? html`<p class="jurisdiction-modal__status">Loading officials…</p>`
            : people.length
              ? renderOfficials(people)
              : html`<p class="jurisdiction-modal__status" role="alert">
                  No officials recorded for this jurisdiction yet.
                </p>`}
        </div>

        <aside class="jurisdiction-modal__aside">
          ${where
            ? html`<p class="jurisdiction-modal__where">${where}</p>`
            : ""}
          ${details ? renderDetails(details.data, details.scraped_at) : ""}
        </aside>
      </div>
    </div>
  `;

  const footer = html`
    <a
      class="jurisdiction-modal__link"
      href="/${jurisdictionOcdidToPath(jurisdictionOcdid)}"
    >
      View in detail <i class="fa-solid fa-arrow-right"></i>
    </a>
    <button class="secondary" @click=${handleClose}>Close</button>
  `;

  return html`
    <civ-modal
      .title=${title}
      .content=${content}
      .footer=${footer}
      .modalProps=${{
        open: Boolean(jurisdictionOcdid),
        onClose: handleClose,
        ariaLabel: title,
      }}
    ></civ-modal>
  `;
}

customElements.define(
  "civ-jurisdiction-modal",
  component(JurisdictionModal as any, {
    useShadowDOM: false,
    observedAttributes: [],
  }),
);
