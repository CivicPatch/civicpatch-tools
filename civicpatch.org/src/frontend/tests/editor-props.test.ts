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
    posts: [],
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
    candidatesOpenFor: null,
    onToggleCandidates: () => {},
    onPickPartner: () => {},
    onAddPost: () => {},
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


const change = (over = {}) =>
  ({
    person_id: "p1",
    disposition: "new",
    role_id: "council-member",
    role_label: "Council Member",
    division_ocdid: "ocd-division/country:us/state:wa/place:x/council_district:5",
    label: null,
    post_label: "Council Member, District 5",
    post_id: "post-5",
    ...over,
  }) as never;

const derivedPostOf = (changes: unknown[]) =>
  personEditorPropsFor(card(), context({ proposals: proposalsByPersonId(changes as never) }))
    .derivedPost;

describe("personEditorPropsFor — derivedPost", () => {
  it("offers the seat the derivation chose, so the Post field is not left saying 'derived'", () =>
    expect(derivedPostOf([change()])).toEqual({
      post_id: "post-5",
      label: "Council Member, District 5",
    }));

  // Ingest stopped minting posts, so this is the ordinary case for a promotion rather than an
  // edge one: the seat exists only as a proposal until somebody publishes.
  it("offers the seat by label when the scrape would mint the post, since there is no row yet", () =>
    expect(derivedPostOf([change({ post_id: null })])).toEqual({
      post_id: null,
      label: "Council Member, District 5",
    }));

  it("offers nothing when nobody is proposed onto a seat", () =>
    expect(derivedPostOf([])).toBe(null));

  // `unmatched` is a vocabulary gap, not an answer.
  it("offers nothing when the derivation could not name the role", () =>
    expect(derivedPostOf([change({ role_id: "unmatched" })])).toBe(null));

  // Two seats is no single answer; picking either would show a decision nobody made.
  it("offers nothing when the person is proposed onto two seats", () =>
    expect(
      derivedPostOf([
        change(),
        change({ role_id: "mayor", post_id: "post-mayor" }),
      ]),
    ).toBe(null));
});

describe("personEditorPropsFor — derivedPost from a held membership", () => {
  // The jurisdiction page passes no proposals: its people are published, so the seat comes
  // from the membership they hold. Without this the Post field there could never answer.
  const withMemberships = (memberships: unknown[]) =>
    personEditorPropsFor(
      card({ newRecord: { id: "p1", name: "A", memberships } }),
      context(),
    ).derivedPost;

  it("offers the seat a published person holds", () =>
    expect(withMemberships([{ post_id: "post-held", post_label: "Mayor" }])).toEqual({
      post_id: "post-held",
      label: "Mayor",
    }));

  it("offers nothing when they hold two seats", () =>
    expect(withMemberships([{ post_id: "a" }, { post_id: "b" }])).toBe(null));

  it("offers nothing when they hold none", () =>
    expect(withMemberships([])).toBe(null));

  it("prefers the proposal over the membership, since a scrape is the newer claim", () =>
    expect(
      personEditorPropsFor(
        card({ newRecord: { id: "p1", name: "A", memberships: [{ post_id: "old" }] } }),
        context({ proposals: proposalsByPersonId([change()]) }),
      ).derivedPost,
    ).toEqual({ post_id: "post-5", label: "Council Member, District 5" }));
});


describe("personEditorPropsFor — onAddPost", () => {
  it("binds the person, because the field control has no id to pass back", () => {
    const asked: string[] = [];
    const props = personEditorPropsFor(
      card({ personId: "p7" }),
      context({ onAddPost: (id: string) => asked.push(id) }),
    );

    props.onAddPost();

    expect(asked).toEqual(["p7"]);
  });
});
