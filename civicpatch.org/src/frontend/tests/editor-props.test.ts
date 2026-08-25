import { describe, it, expect } from "vitest";
import { personEditorPropsFor } from "../components/person-editor/editor-props.js";
import { proposalsByPersonId } from "../components/people/person-cards.js";

// Both renderers in the editor used to compute `office.name` + a friendly division
// themselves, which is why a proposed person's card read empty: they hold no membership,
// and only the proposal knows their post. The subtitle is built once, here.
const card = (over = {}) =>
  ({
    personId: "p1",
    status: "changed",
    oldRecord: null,
    newRecord: { id: "p1", name: "A" },
    surviving: [],
    issues: [],
    ...over,
  }) as never;

const context = (over = {}) =>
  ({
    frozen: new Map(),
    dirtyIds: new Set(),
    isReadOnly: false,
    jurisdictionOcdid: "ocd-jurisdiction/country:us/state:wa/place:x/government",
    officeOptions: [],
    proposals: proposalsByPersonId([]),
    assertions: {},
    isExpanded: () => false,
    onToggleExpand: () => {},
    onPersonSave: () => {},
    onRemovePerson: () => {},
    onUnremovePerson: () => {},
    onRestorePerson: () => {},
    onResetPerson: () => {},
    cards: [],
    mergeOpenId: null,
    onToggleMerge: () => {},
    onPickPartner: () => {},
    ...over,
  }) as never;

const subtitleOf = (cardOver = {}, contextOver = {}) =>
  personEditorPropsFor(card(cardOver), context(contextOver)).subtitle;

describe("personEditorPropsFor — subtitle", () => {
  it("names a proposed person's post, which no record on the card knows", () =>
    expect(
      subtitleOf(
        {},
        {
          proposals: proposalsByPersonId([
            {
              person_id: "p1",
              disposition: "new",
              role_id: "council-member",
              role_label: "Council Member",
              division_ocdid:
                "ocd-division/country:us/state:wa/place:x/council_district:5",
              label: null,
              post_label: "Council Member, District 5",
            },
          ]),
        },
      ),
    ).toBe("Council Member, District 5"));

  it("reads a published person's memberships", () =>
    expect(
      subtitleOf({
        newRecord: {
          id: "p1",
          name: "A",
          memberships: [
            {
              post_id: "x",
              role_id: "mayor",
              role_label: "Mayor",
              division_ocdid: "ocd-division/country:us/state:wa/place:x",
              label: null,
              post_label: "Mayor",
              source_labels: ["Mayor"],
            },
          ],
        },
      }),
    ).toBe("Mayor"));

  it("prefers the proposal over a membership, because the proposal is the pending move", () =>
    expect(
      subtitleOf(
        {
          newRecord: {
            id: "p1",
            name: "A",
            memberships: [
              {
                post_id: "x",
                role_id: "council-member",
                role_label: "Council Member",
                division_ocdid: "ocd-division/country:us/state:wa/place:x",
                label: null,
                post_label: "Council Member",
                source_labels: ["Council Member"],
              },
            ],
          },
        },
        {
          proposals: proposalsByPersonId([
            {
              person_id: "p1",
              disposition: "moved",
              role_id: "mayor",
              role_label: "Mayor",
              division_ocdid: "ocd-division/country:us/state:wa/place:x",
              label: null,
              post_label: "Mayor, At-Large",
            },
          ]),
        },
      ),
      // The proposal carries its own rendered label, because the post may not exist yet for
      // anyone to look one up. The point is that it says Mayor and not Council Member.
    ).toBe("Mayor, At-Large"));
});
