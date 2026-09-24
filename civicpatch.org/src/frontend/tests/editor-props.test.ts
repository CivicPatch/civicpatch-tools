import { describe, it, expect } from "vitest";
import { personEditorPropsFor } from "../components/person-editor/editor-props.js";

// Both renderers in the editor used to compute `office.name` + a friendly division
// themselves, which is why the same person's card read differently in two places. The
// subtitle is built once, here.
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
    roles: [],
    canAssignMembership: false,
    assertions: {},
    overriddenSourceValues: {},
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
    ...over,
  }) as never;

const subtitleOf = (cardOver = {}, contextOver = {}) =>
  personEditorPropsFor(card(cardOver), context(contextOver)).subtitle;

describe("personEditorPropsFor — subtitle", () => {
  // This verified that the subtitle named the scrape's proposed post, which no record on the
  // card knew. It now verifies that it names the office the record itself holds, because the
  // proposed record is the fold's and carries its post like any published one.
  it("names the post the record holds", () =>
    expect(
      subtitleOf({
        newRecord: {
          id: "p1",
          name: "A",
          memberships: [
            {
              post_id: "post-5",
              post_label: "Council Member, District 5",
              label: null,
            },
          ],
        },
      }),
    ).toBe("Council Member, District 5"));

  it("composes the post's own name with the membership's own label", () =>
    expect(
      subtitleOf({
        newRecord: {
          id: "p1",
          name: "A",
          memberships: [{ post_id: "x", post_label: "Mayor", label: "Acting Mayor" }],
        },
      }),
    ).toBe("Mayor, Acting Mayor"));

  it("says nothing when they hold nothing", () =>
    expect(subtitleOf({})).toBe(""));
});


// A membership as the fold's card rows carry it. Until 2026-09-23 these read a separate
// `ProposedChange`, because a proposed post had no row for anyone to name; the fold names it
// from `PostKey`, so the proposed record carries it like any other membership.
const office = (over = {}) =>
  ({
    post_id: "post-5",
    organization_id: "org-1",
    role_id: "council-member",
    role_label: "Council Member",
    post_label: "Council Member, District 5",
    division_ocdid: "ocd-division/country:us/state:wa/place:x/council_district:5",
    label: null,
    ...over,
  }) as never;

const derivedPostOf = (memberships: unknown[], posts: unknown[] = []) =>
  personEditorPropsFor(
    card({ newRecord: { id: "p1", name: "A", memberships } }),
    context({ posts }),
  ).derivedPost;

describe("personEditorPropsFor — derivedPost", () => {
  // This verified that the picker opened on the scrape's proposal. It now verifies that it
  // opens on the office the proposed record holds, because that record is the fold's answer
  // for this changeset and the proposal it used to read is gone.
  it("offers the seat the fold chose, so the Post field is not left saying 'derived'", () =>
    expect(derivedPostOf([office()], [{ id: "post-5", label: "x" }])).toEqual({
      post_id: "post-5",
      label: "Council Member, District 5",
      membershipLabel: null,
      role_id: "council-member",
      division_ocdid: "ocd-division/country:us/state:wa/place:x/council_district:5",
    }));

  // Ingest stopped minting posts, so this is the ordinary case for a promotion rather than an
  // edge one. The fold names the post either way — `PostKey` is a uuid5, row or no row — so
  // what decides is whether the picker's own list has it to look up.
  it("offers the seat by role when the scrape would mint the post, since there is no row yet", () =>
    expect(derivedPostOf([office()], [{ id: "some-other-post" }])).toEqual({
      post_id: null,
      label: "Council Member, District 5",
      membershipLabel: null,
      role_id: "council-member",
      division_ocdid: "ocd-division/country:us/state:wa/place:x/council_district:5",
    }));

  it("keeps the post id while the picker's own list is still loading", () => {
    // `useJurisdictionPosts` answers empty until its fetch lands. Reading that as "the post is
    // not there" would offer every published person's long-standing post by role and division,
    // as though this scrape were about to mint it.
    expect(derivedPostOf([office()], [])?.post_id).toBe("post-5");
  });

  it("offers nothing when they hold no office at all", () =>
    expect(derivedPostOf([])).toBe(null));

  // `unmatched` is a vocabulary gap, not an answer.
  it("offers nothing when the fold could not name the role", () =>
    expect(derivedPostOf([office({ role_id: "unmatched" })])).toBe(null));

  // Two bodies with no body named is no single answer; picking either would show a decision
  // nobody made. Naming one is what the review card and the roster page both do.
  it("offers nothing when they hold offices in two bodies and none is named", () =>
    expect(
      derivedPostOf([office(), office({ post_id: "post-mayor", organization_id: "org-2" })]),
    ).toBe(null));

  it("answers per body once one is named", () =>
    expect(
      personEditorPropsFor(
        card({
          newRecord: {
            id: "p1",
            name: "A",
            memberships: [
              office(),
              office({
                post_id: "post-mayor",
                organization_id: "org-2",
                post_label: "Mayor",
              }),
            ],
          },
        }),
        context({ organizationId: "org-2" }),
      ).derivedPost?.label,
    ).toBe("Mayor"));

  it("carries the membership's own label, so the picker defaults to what the page said", () =>
    expect(derivedPostOf([office({ label: "Chair" })])?.membershipLabel).toBe("Chair"));
});


describe("personEditorPropsFor — office assignment", () => {
  it("passes canAssignMembership through from context unchanged", () =>
    expect(
      personEditorPropsFor(card(), context({ canAssignMembership: true })).canAssignMembership,
    ).toBe(true));

  it("passes roles through from context unchanged, for the office picker's grouping", () => {
    const roles = [{ id: "mayor", label: "Mayor" }];
    expect(personEditorPropsFor(card(), context({ roles })).roles).toBe(roles);
  });
});
