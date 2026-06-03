import { describe, it, expect } from "vitest";
import { moveUp, moveDown, moveToTop, applyDrop } from "../components/role-reorder/reorder-utils.js";

describe("moveUp", () => {
  it("swaps an item with the one above it", () => {
    expect(moveUp(["a", "b", "c"], 1)).toEqual(["b", "a", "c"]);
  });

  it("is a no-op at the top", () => {
    const order = ["a", "b", "c"];
    expect(moveUp(order, 0)).toBe(order);
  });

  it("does not mutate the input", () => {
    const order = ["a", "b"];
    moveUp(order, 1);
    expect(order).toEqual(["a", "b"]);
  });
});

describe("moveDown", () => {
  it("swaps an item with the one below it", () => {
    expect(moveDown(["a", "b", "c"], 1)).toEqual(["a", "c", "b"]);
  });

  it("is a no-op at the bottom", () => {
    const order = ["a", "b", "c"];
    expect(moveDown(order, 2)).toBe(order);
  });
});

describe("moveToTop", () => {
  it("moves an item to the front, shifting the rest down", () => {
    expect(moveToTop(["a", "b", "c"], 2)).toEqual(["c", "a", "b"]);
  });

  it("is a no-op when already at the top", () => {
    const order = ["a", "b"];
    expect(moveToTop(order, 0)).toBe(order);
  });
});

describe("applyDrop", () => {
  it("moves an item down to the drop index", () => {
    expect(applyDrop(["a", "b", "c", "d"], 0, 2)).toEqual(["b", "c", "a", "d"]);
  });

  it("moves an item up to the drop index", () => {
    expect(applyDrop(["a", "b", "c", "d"], 3, 1)).toEqual(["a", "d", "b", "c"]);
  });

  it("is a no-op when source equals target", () => {
    const order = ["a", "b", "c"];
    expect(applyDrop(order, 1, 1)).toBe(order);
  });
});
