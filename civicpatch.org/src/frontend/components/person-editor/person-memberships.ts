// The person editor's membership section: every organization this person sits in, and the post
// they hold there. It reads; the office itself is picked in the roster row, and removing
// somebody from a body is that row dropping its office.

import { html, nothing } from "lit-html";
import "./person-memberships.css";
import { type RosterMembership } from "../../schemas/roster-membership.js";
import {
  membershipTitle,
  membershipsByOrganization,
  pageWordings,
  type OrganizationMemberships,
} from "./person-memberships-model.js";

export interface RosterMembershipsProps {
  personId: string;
  memberships: RosterMembership[];
}

function renderLine(membership: RosterMembership) {
  const title = membershipTitle(membership);
  const wordings = pageWordings(membership, title);
  return html`<div class="person-memberships__line">
    <span class="person-memberships__post">${title}</span>
    ${wordings.length
      ? html`<div class="person-memberships__meta">
          <span class="person-memberships__meta-key">page said</span>
          ${wordings.join(", ")}
        </div>`
      : nothing}
  </div>`;
}

function renderSection(section: OrganizationMemberships) {
  return html`<div class="person-memberships__org">
    <div class="person-memberships__orghead">${section.organizationName}</div>
    ${section.memberships.map(renderLine)}
  </div>`;
}

export function renderRosterMemberships(props: RosterMembershipsProps) {
  const sections = membershipsByOrganization(props.memberships, props.personId);
  if (!sections.length) return nothing;
  return html`<div class="person-memberships">
    ${sections.map(renderSection)}
  </div>`;
}
