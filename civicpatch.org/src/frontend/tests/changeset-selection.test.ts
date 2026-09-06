// The compare strip's whole behaviour lives in these three functions. Testing the states here
// is what the plan asks for instead of testing the render.

import { describe, expect, it } from "vitest";

import {
  hasPickedEverything,
  isShown,
  toggle,
} from "../pages/changeset-summaries-page/selection.ts";

describe("isShown", () => {
  it("shows every state when nothing is picked", () => {
    // The resting state is everything, not nothing — there is no empty view to fall into.
    expect(isShown([], "wa")).toBe(true);
  });

  it("hides a state once some other state is picked", () => {
    expect(isShown(["tn"], "wa")).toBe(false);
    expect(isShown(["tn"], "tn")).toBe(true);
  });
});

describe("toggle", () => {
  it("adds a state that is not picked and removes one that is", () => {
    expect(toggle([], "wa")).toEqual(["wa"]);
    expect(toggle(["wa", "tn"], "wa")).toEqual(["tn"]);
  });

  it("does not mutate the selection it was given", () => {
    const picked = ["wa"];
    toggle(picked, "tn");
    expect(picked).toEqual(["wa"]);
  });
});

describe("hasPickedEverything", () => {
  it("is false for an empty selection even though it renders the same rows", () => {
    // They render alike; they differ in what unpicking one state leaves behind.
    expect(hasPickedEverything([], 50)).toBe(false);
    expect(hasPickedEverything(["wa"], 1)).toBe(true);
  });
});
