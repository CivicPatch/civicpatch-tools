// The person editor's membership section: every organization this person sits in, and the two
// claims about one post. Both are withdrawable, so each button is a toggle back to "no claim"
// rather than a separate undo.
//
// Everything here is scoped to a post, which is what keeps the two readable: one says the term
// ended, the other says it was never true. The person-scoped claim ("they are not ours at all")
// is Remove, in the editor's action bar, because a button that empties every section does not
// belong inside one of them. Deleting the person is neither: it destroys history rather than
// claiming anything, and is maintainers-only.

import { html, nothing } from "lit-html";
import "./person-memberships.css";
import {
  MEMBERSHIP_REMOVAL,
  type MembershipRemoval,
  type RosterMembership,
} from "../../schemas/membership-removal.js";
import {
  membershipTitle,
  membershipsByOrganization,
  nextRemoval,
  pageWordings,
  type OrganizationMemberships,
} from "./person-memberships-model.js";

export interface RosterMembershipsProps {
  personId: string;
  memberships: RosterMembership[];
  isReadOnly: boolean;
  // null where the claims do not belong: a review asks whether the scrape picked this person up
  // correctly, and closing a membership corrects published data instead of answering that. The
  // sections still render, because where somebody already sits is part of judging the scrape.
  onSetRemoval: ((membershipId: string, assertion: MembershipRemoval) => void) | null;
}

const ACTS: { assertion: MembershipRemoval; label: string; chosen: string }[] = [
  {
    assertion: MEMBERSHIP_REMOVAL.CLOSED,
    label: "Close membership",
    chosen: "Closing at publish",
  },
  {
    assertion: MEMBERSHIP_REMOVAL.NEVER_HELD,
    label: "Never held this post",
    chosen: "Never held this post",
  },
];

function renderActs(membership: RosterMembership, props: RosterMembershipsProps) {
  const onSetRemoval = props.onSetRemoval;
  if (props.isReadOnly || !onSetRemoval) return nothing;
  return html`<div class="person-memberships__acts">
    ${ACTS.map(({ assertion, label, chosen }) => {
      const isChosen = membership.removal_assertion === assertion;
      return html`<button
        type="button"
        class="person-memberships__act"
        aria-pressed=${isChosen}
        @click=${() =>
          onSetRemoval(
            membership.id,
            nextRemoval(membership.removal_assertion, assertion),
          )}
      >
        ${isChosen ? chosen : label}
      </button>`;
    })}
  </div>`;
}

function renderLine(membership: RosterMembership, props: RosterMembershipsProps) {
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
    ${renderActs(membership, props)}
  </div>`;
}

function renderSection(section: OrganizationMemberships, props: RosterMembershipsProps) {
  return html`<div class="person-memberships__org">
    <div class="person-memberships__orghead">${section.organizationName}</div>
    ${section.memberships.map((membership) => renderLine(membership, props))}
  </div>`;
}

export function renderRosterMemberships(props: RosterMembershipsProps) {
  const sections = membershipsByOrganization(props.memberships, props.personId);
  if (!sections.length) return nothing;
  return html`<div class="person-memberships">
    ${sections.map((section) => renderSection(section, props))}
  </div>`;
}
