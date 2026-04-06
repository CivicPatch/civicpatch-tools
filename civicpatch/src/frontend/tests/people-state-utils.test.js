import { describe, it, expect } from "vitest";
import { applyUpdate, mergeFields, collapseInto, TRACKED_FIELDS } from "../components/edit-people/hooks/people-state-utils.js";

const person = (overrides = {}) => ({
  id: "a",
  name: "Alice",
  image: null,
  cdn_image: null,
  start_date: null,
  end_date: null,
  updated_at: null,
  other_names: [],
  phones: [],
  emails: [],
  urls: [],
  source_urls: [],
  office: { name: "Mayor" },
  _dirty: false,
  _changes: [],
  _selected: false,
  ...overrides,
});

// ── applyUpdate ──────────────────────────────────────────────────────────────

describe("applyUpdate", () => {
  it("merges updates onto person", () => {
    const result = applyUpdate(person(), { name: "Alicia" }, person());
    expect(result.name).toBe("Alicia");
  });

  it("marks dirty when a tracked field changes", () => {
    const original = person();
    const result = applyUpdate(person(), { name: "Alicia" }, original);
    expect(result._dirty).toBe(true);
    expect(result._changes).toContain("name");
  });

  it("not dirty when nothing changed", () => {
    const p = person();
    const result = applyUpdate(p, { name: "Alice" }, p);
    expect(result._dirty).toBe(false);
  });

  it("marks dirty on _deleted", () => {
    const p = person();
    const result = applyUpdate(p, { _deleted: true }, p);
    expect(result._dirty).toBe(true);
  });
});

// ── mergeFields ──────────────────────────────────────────────────────────────

describe("mergeFields", () => {
  it("survivor name is preserved", () => {
    const a = person({ id: "a", name: "Alice" });
    const b = person({ id: "b", name: "Bob" });
    const result = mergeFields(a, [b]);
    expect(result.name).toBe("Alice");
  });

  it("absorbed name added to other_names", () => {
    const a = person({ id: "a", name: "Alice", other_names: [] });
    const b = person({ id: "b", name: "Bob" });
    const result = mergeFields(a, [b]);
    expect(result.other_names).toContain("Bob");
  });

  it("survivor name not added to other_names", () => {
    const a = person({ id: "a", name: "Alice", other_names: [] });
    const b = person({ id: "b", name: "Bob" });
    const result = mergeFields(a, [b]);
    expect(result.other_names).not.toContain("Alice");
  });

  it("unions array fields", () => {
    const a = person({ id: "a", phones: ["111"] });
    const b = person({ id: "b", phones: ["222"] });
    const result = mergeFields(a, [b]);
    expect(result.phones).toEqual(expect.arrayContaining(["111", "222"]));
  });

  it("deduplicates array fields", () => {
    const a = person({ id: "a", phones: ["111"] });
    const b = person({ id: "b", phones: ["111"] });
    const result = mergeFields(a, [b]);
    expect(result.phones.filter(p => p === "111")).toHaveLength(1);
  });

  it("merges office names with separator", () => {
    const a = person({ id: "a", office: { name: "Mayor" } });
    const b = person({ id: "b", office: { name: "Council Member" } });
    const result = mergeFields(a, [b]);
    expect(result.office.name).toBe("Mayor - Council Member");
  });

  it("deduplicates office names", () => {
    const a = person({ id: "a", office: { name: "Mayor" } });
    const b = person({ id: "b", office: { name: "Mayor" } });
    const result = mergeFields(a, [b]);
    expect(result.office.name).toBe("Mayor");
  });

  it("marks result dirty with all tracked changes", () => {
    const result = mergeFields(person(), [person({ id: "b" })]);
    expect(result._dirty).toBe(true);
    expect(result._changes).toEqual(TRACKED_FIELDS);
  });
});

// ── collapseInto ─────────────────────────────────────────────────────────────

describe("collapseInto", () => {
  it("removes both survivor and absorbed from list, adds merged", () => {
    const a = person({ id: "a", name: "Alice" });
    const b = person({ id: "b", name: "Bob" });
    const c = person({ id: "c", name: "Carol" });
    const result = collapseInto(a, b, [a, b, c]);
    const ids = result.map(p => p.id);
    expect(ids).not.toContain("b");
    expect(ids).toContain("a");
    expect(ids).toContain("c");
  });

  it("absorbed name appears in merged other_names", () => {
    const a = person({ id: "a", name: "Alice" });
    const b = person({ id: "b", name: "Bob" });
    const result = collapseInto(a, b, [a, b]);
    const merged = result.find(p => p.id === "a");
    expect(merged.other_names).toContain("Bob");
  });
});
