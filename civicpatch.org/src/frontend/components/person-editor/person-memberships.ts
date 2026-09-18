// The person editor's membership section: every organization this person sits in, and the two
// claims that take them off a roster. Both are withdrawable, so each button is a toggle back to
// "no claim" rather than a separate undo. Deleting the person is not here: it destroys history and
// lives in the editor's own action bar, behind a stricter permission.

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
  type OrganizationMemberships,
} from "./person-memberships-model.js";

export interface RosterMembershipsProps {
  personId: string;
  memberships: RosterMembership[];
  isReadOnly: boolean;
  onSetRemoval: (membershipId: string, assertion: MembershipRemoval) => void;
  onSetNotAMember: (personId: string, claimed: boolean) => void;
}

const ACTS: { assertion: MembershipRemoval; label: string; chosen: string }[] = [
  {
    assertion: MEMBERSHIP_REMOVAL.CLOSED,
    label: "Close membership",
    chosen: "Closing at publish",
  },
  {
    assertion: MEMBERSHIP_REMOVAL.NEVER_HELD,
    label: "Never held this",
    chosen: "Never held this",
  },
];

function renderActs(membership: RosterMembership, props: RosterMembershipsProps) {
  if (props.isReadOnly) return nothing;
  return html`<div class="person-memberships__acts">
    ${ACTS.map(({ assertion, label, chosen }) => {
      const isChosen = membership.removal_assertion === assertion;
      return html`<button
        type="button"
        class="person-memberships__act"
        aria-pressed=${isChosen}
        @click=${() =>
          props.onSetRemoval(
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
  const sources = membership.source_labels ?? [];
  return html`<div class="person-memberships__line">
    <span class="person-memberships__post">${membershipTitle(membership)}</span>
    ${sources.length
      ? html`<div class="person-memberships__meta">${sources.join(", ")}</div>`
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

// The person-level half, under every section rather than inside one: it says the record does not
// belong to this jurisdiction at all, which is a different claim from leaving one organization.
function renderNotAMember(claimed: boolean, props: RosterMembershipsProps) {
  if (props.isReadOnly) return nothing;
  return html`<div class="person-memberships__line person-memberships__line--person">
    <div class="person-memberships__acts">
      <button
        type="button"
        class="person-memberships__act"
        aria-pressed=${claimed}
        @click=${() => props.onSetNotAMember(props.personId, !claimed)}
      >
        ${claimed ? "Not a member here" : "Not a member here?"}
      </button>
    </div>
  </div>`;
}

export function renderRosterMemberships(props: RosterMembershipsProps) {
  const sections = membershipsByOrganization(props.memberships, props.personId);
  if (!sections.length) return nothing;
  const notAMember = sections[0].memberships[0].not_a_member;
  return html`<div class="person-memberships">
    ${sections.map((section) => renderSection(section, props))}
    ${renderNotAMember(notAMember, props)}
  </div>`;
}
