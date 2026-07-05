import { describe, it, expect } from "vitest";
import {
  getFieldValue,
  diffValue,
  fieldDiffState,
  multiValueDiff,
  recordsDiffer,
  isValidDate,
  isTermOrderValid,
  isRequiredFieldEmpty,
  fieldError,
  buildLinkUpdates,
  indexIssuesByPersonId,
  type FieldSpec,
  type Issue,
} from "../components/people-diff/diff-model.js";

const IMAGE_FIELD: FieldSpec = { key: "image", label: "Photo", type: "image" };

describe("getFieldValue", () => {
  it("reads a top-level key", () => {
    expect(getFieldValue({ name: "Maria" }, "name")).toBe("Maria");
  });

  it("reads a dotted path", () => {
    expect(getFieldValue({ office: { name: "Mayor" } }, "office.name")).toBe("Mayor");
  });

  it("returns undefined for a missing nested path without throwing", () => {
    expect(getFieldValue({}, "office.name")).toBeUndefined();
  });
});

describe("diffValue", () => {
  it("prefers cdn_image over image for the photo field", () => {
    expect(diffValue({ image: "raw.jpg", cdn_image: "cdn.jpg" }, IMAGE_FIELD)).toBe("cdn.jpg");
  });

  it("falls back to image when cdn_image is absent (the new side)", () => {
    expect(diffValue({ image: "raw.jpg" }, IMAGE_FIELD)).toBe("raw.jpg");
  });

  it("returns the field value for non-image fields", () => {
    const field: FieldSpec = { key: "name", label: "Name", type: "text" };
    expect(diffValue({ name: "Maria" }, field)).toBe("Maria");
  });
});

describe("fieldDiffState (text)", () => {
  it("is same for equal values (whitespace-insensitive)", () => {
    expect(fieldDiffState("Mayor", " Mayor ", "text")).toBe("same");
  });

  it("is added when old is empty", () => {
    expect(fieldDiffState("", "Mayor", "text")).toBe("added");
  });

  it("is cleared when new is empty", () => {
    expect(fieldDiffState("Mayor", "", "text")).toBe("cleared");
  });

  it("is changed when both present and differ", () => {
    expect(fieldDiffState("Mayor", "Council", "text")).toBe("changed");
  });

  it("treats a date precision change as changed (no 'refined' state)", () => {
    expect(fieldDiffState("2021", "2021-01-04", "date")).toBe("changed");
  });
});

describe("fieldDiffState (image, presence-only)", () => {
  it("is same when both sides have a photo, even if the URLs differ", () => {
    expect(fieldDiffState("cdn.jpg", "raw.jpg", "image")).toBe("same");
  });

  it("is added when only the new side has a photo", () => {
    expect(fieldDiffState("", "raw.jpg", "image")).toBe("added");
  });

  it("is cleared when only the old side had a photo", () => {
    expect(fieldDiffState("cdn.jpg", "", "image")).toBe("cleared");
  });
});

describe("multiValueDiff", () => {
  it("flags new-only values as added and old-only as removed", () => {
    const diff = multiValueDiff(["a@x.gov"], ["a@x.gov", "b@x.gov"]);
    expect(diff).toEqual([
      { value: "a@x.gov", status: "both" },
      { value: "b@x.gov", status: "added" },
    ]);
  });

  it("appends old-only values flagged removed", () => {
    const diff = multiValueDiff(["old@x.gov"], ["new@x.gov"]);
    expect(diff).toEqual([
      { value: "new@x.gov", status: "added" },
      { value: "old@x.gov", status: "removed" },
    ]);
  });

  it("matches case- and whitespace-insensitively", () => {
    const diff = multiValueDiff(["A@X.gov"], [" a@x.gov "]);
    expect(diff).toEqual([{ value: " a@x.gov ", status: "both" }]);
  });

  it("handles empty inputs", () => {
    expect(multiValueDiff([], [])).toEqual([]);
  });
});

describe("recordsDiffer", () => {
  const base = {
    name: "Maria",
    office: { name: "Mayor", division_ocdid: null },
    start_date: "2021",
    end_date: "2025",
    emails: ["m@x.gov"],
    phones: [],
    urls: [],
    other_names: [],
    image: "p.jpg",
  };

  it("is false for identical records", () => {
    expect(recordsDiffer(base, { ...base })).toBe(false);
  });

  it("is true when a scalar field differs", () => {
    expect(recordsDiffer(base, { ...base, office: { name: "Council", division_ocdid: null } })).toBe(true);
  });

  it("is true when a multi field gains a value", () => {
    expect(recordsDiffer(base, { ...base, emails: ["m@x.gov", "m2@x.gov"] })).toBe(true);
  });

  it("ignores photo URL differences (presence-only)", () => {
    expect(recordsDiffer({ ...base, cdn_image: "cdn.jpg" }, { ...base, image: "raw.jpg" })).toBe(false);
  });

  it("ignores source_urls (documentation, not diffed)", () => {
    expect(recordsDiffer({ ...base, source_urls: ["a"] }, { ...base, source_urls: ["b", "c"] })).toBe(false);
  });
});

describe("isRequiredFieldEmpty", () => {
  const nameField: FieldSpec = { key: "name", label: "Name", type: "text", required: true };
  const divisionField: FieldSpec = { key: "office.division_ocdid", label: "Division", type: "text", required: true };
  const emailField: FieldSpec = { key: "emails", label: "Email", type: "multi" };

  it("flags an empty required scalar", () => {
    expect(isRequiredFieldEmpty({ name: "" }, nameField)).toBe(true);
    expect(isRequiredFieldEmpty({ office: { division_ocdid: null } }, divisionField)).toBe(true);
  });

  it("passes a filled required field", () => {
    expect(isRequiredFieldEmpty({ name: "Maria" }, nameField)).toBe(false);
  });

  it("never flags an optional field", () => {
    expect(isRequiredFieldEmpty({ emails: [] }, emailField)).toBe(false);
  });
});

describe("isValidDate", () => {
  it.each(["", "2024", "2024-06", "2024-06-19"])("accepts %s", (value) => {
    expect(isValidDate(value)).toBe(true);
  });

  it.each(["24", "2024/06", "2024-6", "June 2024"])("rejects %s", (value) => {
    expect(isValidDate(value)).toBe(false);
  });
});

describe("isTermOrderValid", () => {
  it("accepts start before end", () => {
    expect(isTermOrderValid("2021", "2025")).toBe(true);
  });

  it("pads partial dates: 2024 start vs 2024-06 end is valid", () => {
    expect(isTermOrderValid("2024", "2024-06")).toBe(true);
  });

  it("rejects start after end", () => {
    expect(isTermOrderValid("2025", "2021")).toBe(false);
  });

  it("does not flag indeterminate input (empty or malformed)", () => {
    expect(isTermOrderValid("", "2025")).toBe(true);
    expect(isTermOrderValid("nope", "2025")).toBe(true);
  });
});

describe("fieldError", () => {
  const nameField: FieldSpec = { key: "name", label: "Name", type: "text", required: true };
  const startField: FieldSpec = { key: "start_date", label: "Term start", type: "date" };
  const endField: FieldSpec = { key: "end_date", label: "Term end", type: "date" };

  it("flags a required field left empty", () => {
    expect(fieldError(nameField, { name: "" })).toBe("Required");
  });

  it("flags a malformed date", () => {
    expect(fieldError(startField, { start_date: "20-24" })).toBe("Use YYYY, YYYY-MM, or YYYY-MM-DD");
  });

  it("flags term end before term start", () => {
    expect(fieldError(endField, { start_date: "2025", end_date: "2021" })).toBe("Term end is before term start");
  });

  it("returns null for a valid field", () => {
    expect(fieldError(nameField, { name: "Maria" })).toBeNull();
    expect(fieldError(endField, { start_date: "2021", end_date: "2025" })).toBeNull();
  });
});

describe("buildLinkUpdates", () => {
  it("adopts the target's id", () => {
    const result = buildLinkUpdates({ id: "new", name: "Bob" }, { id: "old", name: "Robert" });
    expect(result.id).toBe("old");
  });

  it("folds the target's old name into other_names as an alias", () => {
    const result = buildLinkUpdates({ id: "new", name: "Bob Smith" }, { id: "old", name: "Robert Smith" });
    expect(result.other_names).toContain("Robert Smith");
  });

  it("keeps both the target's and the added person's existing aliases", () => {
    const added = { id: "new", name: "Bob", other_names: ["Bobby"] };
    const target = { id: "old", name: "Robert", other_names: ["Rob"] };
    expect(buildLinkUpdates(added, target).other_names).toEqual(["Robert", "Rob", "Bobby"]);
  });

  it("drops the added person's own name from the aliases", () => {
    const added = { id: "new", name: "Bob" };
    const target = { id: "old", name: "Bob", other_names: ["Bob"] };
    expect(buildLinkUpdates(added, target).other_names).not.toContain("Bob");
  });

  it("dedupes aliases", () => {
    const added = { id: "new", name: "Bob", other_names: ["Rob"] };
    const target = { id: "old", name: "Robert", other_names: ["Rob", "Robert"] };
    expect(buildLinkUpdates(added, target).other_names).toEqual(["Robert", "Rob"]);
  });

  it("handles records with no aliases", () => {
    const result = buildLinkUpdates({ id: "new", name: "Bob" }, { id: "old", name: "Robert" });
    expect(result.other_names).toEqual(["Robert"]);
  });
});

describe("indexIssuesByPersonId", () => {
  const extra: Issue = { code: "extra_official", message: "Extra official: Jane", person_ids: ["p2"] };
  const dup: Issue = {
    code: "duplicate_unique_role",
    message: "Role 'mayor' held by multiple officials",
    person_ids: ["p1", "p2"],
    field: "office.name",
  };

  it("anchors an issue to each person it names", () => {
    const byId = indexIssuesByPersonId([dup]);
    expect(byId.get("p1")).toEqual([dup]);
    expect(byId.get("p2")).toEqual([dup]);
  });

  it("collects multiple issues on the same card", () => {
    const byId = indexIssuesByPersonId([extra, dup]);
    expect(byId.get("p2")).toEqual([extra, dup]);
  });

  it("omits list-level issues (no person_ids)", () => {
    const missing: Issue = { code: "missing_official", message: "Missing official: Bob", person_ids: [] };
    const legacy: Issue = { code: "legacy", message: "Only 2 people found" };
    const byId = indexIssuesByPersonId([missing, legacy]);
    expect(byId.size).toBe(0);
  });
});
