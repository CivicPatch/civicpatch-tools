import { describe, it, expect } from "vitest";
import {
  getFieldValue,
  diffValue,
  fieldDiffState,
  multiValueDiff,
  multiValueState,
  fieldState,
  changedFields,
  recordsDiffer,
  survivingFields,
  isValidDate,
  isTermOrderValid,
  isRequiredFieldEmpty,
  fieldError,
  type FieldSpec,
  type Issue,
} from "../components/review/field-model.js";
import {
  foldRemovals,
  indexIssuesByPersonId,
} from "../components/review/review-cards.js";

const IMAGE_FIELD: FieldSpec = { key: "image", label: "Photo", type: "image" };

describe("getFieldValue", () => {
  it("reads a top-level key", () => {
    expect(getFieldValue({ name: "Maria" }, "name")).toBe("Maria");
  });

  it("reads a dotted path", () => {
    expect(getFieldValue({ office: { name: "Mayor" } }, "office.name")).toBe(
      "Mayor",
    );
  });

  it("returns undefined for a missing nested path without throwing", () => {
    expect(getFieldValue({}, "office.name")).toBeUndefined();
  });
});

describe("diffValue", () => {
  it("prefers cdn_image over image for the photo field", () => {
    expect(
      diffValue({ image: "raw.jpg", cdn_image: "cdn.jpg" }, IMAGE_FIELD),
    ).toBe("cdn.jpg");
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
    expect(
      recordsDiffer(base, {
        ...base,
        office: { name: "Council", division_ocdid: null },
      }),
    ).toBe(true);
  });

  it("is true when a multi field gains a value", () => {
    expect(
      recordsDiffer(base, { ...base, emails: ["m@x.gov", "m2@x.gov"] }),
    ).toBe(true);
  });

  it("ignores photo URL differences (presence-only)", () => {
    expect(
      recordsDiffer(
        { ...base, cdn_image: "cdn.jpg" },
        { ...base, image: "raw.jpg" },
      ),
    ).toBe(false);
  });

  it("ignores source_urls (documentation, not diffed)", () => {
    expect(
      recordsDiffer(
        { ...base, source_urls: ["a"] },
        { ...base, source_urls: ["b", "c"] },
      ),
    ).toBe(false);
  });
});

describe("multiValueState", () => {
  it("is same when both sides hold the same values, order-insensitively", () => {
    expect(
      multiValueState(["a@x.gov", "b@x.gov"], ["b@x.gov", "a@x.gov"]),
    ).toBe("same");
  });

  it("is added when the new side only gains", () => {
    expect(multiValueState(["a@x.gov"], ["a@x.gov", "b@x.gov"])).toBe("added");
  });

  it("is cleared when the new side only loses", () => {
    expect(multiValueState(["a@x.gov", "b@x.gov"], ["a@x.gov"])).toBe(
      "cleared",
    );
  });

  it("is changed when it both gains and loses", () => {
    expect(multiValueState(["a@x.gov"], ["b@x.gov"])).toBe("changed");
  });

  it("is same for two empty lists", () => {
    expect(multiValueState([], [])).toBe("same");
  });
});

describe("fieldState", () => {
  const nameField: FieldSpec = { key: "name", label: "Name", type: "text" };
  const emailField: FieldSpec = {
    key: "emails",
    label: "Email",
    type: "multi",
  };
  const sourcesField: FieldSpec = {
    key: "source_urls",
    label: "Source urls",
    type: "multi",
    diff: false,
  };

  it("dispatches multi fields to the multi-value verdict", () => {
    expect(
      fieldState(
        emailField,
        { id: "1", emails: [] },
        { id: "1", emails: ["a@x.gov"] },
      ),
    ).toBe("added");
  });

  it("dispatches scalar fields to the scalar verdict", () => {
    expect(
      fieldState(
        nameField,
        { id: "1", name: "Maria" },
        { id: "1", name: "Marie" },
      ),
    ).toBe("changed");
  });

  it("is always same for a field marked diff: false", () => {
    expect(
      fieldState(
        sourcesField,
        { id: "1", source_urls: ["a"] },
        { id: "1", source_urls: ["b"] },
      ),
    ).toBe("same");
  });

  it("treats a missing old record as an empty side (an added person)", () => {
    expect(fieldState(nameField, null, { id: "1", name: "Maria" })).toBe(
      "added",
    );
  });

  it("treats a missing new record as an empty side (a person the scrape lost)", () => {
    expect(fieldState(nameField, { id: "1", name: "Maria" }, null)).toBe(
      "cleared",
    );
  });

  it("compares photos on presence only", () => {
    expect(
      fieldState(
        IMAGE_FIELD,
        { id: "1", cdn_image: "cdn.jpg" },
        { id: "1", image: "raw.jpg" },
      ),
    ).toBe("same");
  });
});

describe("changedFields", () => {
  const base = {
    id: "1",
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

  it("is empty for identical records", () => {
    expect(changedFields(base, { ...base })).toEqual([]);
  });

  it("reports only the fields that differ, with their state", () => {
    const changes = changedFields(base, {
      ...base,
      end_date: "2027",
      emails: [],
    });
    expect(changes.map((c) => [c.field.key, c.state])).toEqual([
      ["end_date", "changed"],
      ["emails", "cleared"],
    ]);
  });

  it("returns fields in schema order, not the order they were edited", () => {
    const changes = changedFields(base, { ...base, emails: [], name: "Marie" });
    expect(changes.map((c) => c.field.key)).toEqual(["name", "emails"]);
  });

  it("excludes source_urls even when it differs", () => {
    const changes = changedFields(
      { ...base, source_urls: ["a"] },
      { ...base, source_urls: ["b"] },
    );
    expect(changes).toEqual([]);
  });

  it("reports every populated field of an added person, and no empty ones", () => {
    const added = {
      id: "2",
      name: "Ada",
      office: { name: "Councilor" },
      emails: [],
      phones: [],
    };
    expect(changedFields(null, added).map((c) => c.field.key)).toEqual([
      "name",
      "office.name",
    ]);
  });

  it("agrees with recordsDiffer by construction", () => {
    const changed = { ...base, name: "Marie" };
    expect(recordsDiffer(base, changed)).toBe(
      changedFields(base, changed).length > 0,
    );
    expect(recordsDiffer(base, { ...base })).toBe(
      changedFields(base, { ...base }).length > 0,
    );
  });
});

describe("isRequiredFieldEmpty", () => {
  const nameField: FieldSpec = {
    key: "name",
    label: "Name",
    type: "text",
    required: true,
  };
  const divisionField: FieldSpec = {
    key: "office.division_ocdid",
    label: "Division",
    type: "text",
    required: true,
  };
  const emailField: FieldSpec = {
    key: "emails",
    label: "Email",
    type: "multi",
  };

  it("flags an empty required scalar", () => {
    expect(isRequiredFieldEmpty({ name: "" }, nameField)).toBe(true);
    expect(
      isRequiredFieldEmpty({ office: { division_ocdid: null } }, divisionField),
    ).toBe(true);
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
  const nameField: FieldSpec = {
    key: "name",
    label: "Name",
    type: "text",
    required: true,
  };
  const startField: FieldSpec = {
    key: "start_date",
    label: "Term start",
    type: "date",
  };
  const endField: FieldSpec = {
    key: "end_date",
    label: "Term end",
    type: "date",
  };

  it("flags a required field left empty", () => {
    expect(fieldError(nameField, { name: "" })).toBe("Required");
  });

  it("flags a malformed date", () => {
    expect(fieldError(startField, { start_date: "20-24" })).toBe(
      "Use YYYY, YYYY-MM, or YYYY-MM-DD",
    );
  });

  it("flags term end before term start", () => {
    expect(fieldError(endField, { start_date: "2025", end_date: "2021" })).toBe(
      "Term end is before term start",
    );
  });

  it("returns null for a valid field", () => {
    expect(fieldError(nameField, { name: "Maria" })).toBeNull();
    expect(
      fieldError(endField, { start_date: "2021", end_date: "2025" }),
    ).toBeNull();
  });
});

describe("indexIssuesByPersonId", () => {
  const extra: Issue = {
    code: "extra_official",
    message: "Extra official: Jane",
    person_ids: ["p2"],
  };
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
    const missing: Issue = {
      code: "missing_official",
      message: "Dropped official: Bob",
      person_ids: [],
    };
    const legacy: Issue = { code: "legacy", message: "Only 2 people found" };
    const byId = indexIssuesByPersonId([missing, legacy]);
    expect(byId.size).toBe(0);
  });
});

describe("foldRemovals", () => {
  const entry = (type: string, id: string) => ({
    type,
    person: { id },
    from: null,
  });
  const result = (diffEntries: any[], unchangedEntries: any[]) => ({
    diffEntries,
    unchangedEntries,
  });

  it("leaves everything alone when nothing is deleted", () => {
    const input = result([entry("changed", "a")], [entry("unchanged", "b")]);
    expect(foldRemovals(input, new Set())).toEqual(input);
  });

  it("re-types a deleted existing person as removed", () => {
    const folded = foldRemovals(
      result([entry("changed", "a")], []),
      new Set(["a"]),
    );
    expect(folded.diffEntries.map((e) => e.type)).toEqual(["removed"]);
  });

  it("re-types a deleted added person as removed, rather than dropping them", () => {
    const folded = foldRemovals(
      result([entry("added", "a")], []),
      new Set(["a"]),
    );
    expect(folded.diffEntries.map((e) => e.type)).toEqual(["removed"]);
  });

  it("moves a deleted unchanged person out of the unchanged bucket", () => {
    const folded = foldRemovals(
      result([], [entry("unchanged", "a")]),
      new Set(["a"]),
    );
    expect(folded.unchangedEntries).toEqual([]);
    expect(folded.diffEntries.map((e) => e.type)).toEqual(["removed"]);
  });

  it("keeps the new-side record, so the card can still offer Undo", () => {
    const folded = foldRemovals(
      result([], [entry("unchanged", "a")]),
      new Set(["a"]),
    );
    expect(folded.diffEntries[0].person.id).toBe("a");
  });

  it("folds only the deleted people, leaving their neighbours untouched", () => {
    const input = result(
      [entry("changed", "a"), entry("added", "b")],
      [entry("unchanged", "c")],
    );
    const folded = foldRemovals(input, new Set(["a"]));
    expect(folded.diffEntries.map((e) => [e.person.id, e.type])).toEqual([
      ["a", "removed"],
      ["b", "added"],
    ]);
    expect(folded.unchangedEntries.map((e) => e.person.id)).toEqual(["c"]);
  });
});

describe("survivingFields", () => {
  const whole = {
    id: "1",
    name: "Maria",
    office: {
      name: "Mayor",
      division_ocdid: "ocd-division/country:us/state:nh/place:concord",
    },
    start_date: "2021",
    end_date: "2025",
    emails: ["m@x.gov"],
    phones: [],
    urls: [],
    other_names: [],
    image: "p.jpg",
  };
  const keys = (result: { field: FieldSpec }[]) =>
    result.map((s) => s.field.key);

  it("shows nothing when a complete record is unchanged", () => {
    // Only source_urls, which is always visible by design.
    expect(keys(survivingFields(whole, { ...whole }))).toEqual(["source_urls"]);
  });

  it("shows a field that differs, with its diff state", () => {
    const surviving = survivingFields(whole, { ...whole, end_date: "2027" });
    expect(surviving.map((s) => [s.field.key, s.state, s.reason])).toEqual([
      ["end_date", "changed", "diff"],
      ["source_urls", "same", "context"],
    ]);
  });

  it("shows an unchanged field an issue anchors to — rule 2's whole purpose", () => {
    const issue: Issue = {
      code: "duplicate_unique_role",
      message: "…",
      field: "office.name",
    };
    const surviving = survivingFields(whole, { ...whole }, [issue]);
    expect(surviving.map((s) => [s.field.key, s.state, s.reason])).toEqual([
      ["office.name", "same", "issue"],
      ["source_urls", "same", "context"],
    ]);
  });

  it("ignores a person-level issue that anchors to no field", () => {
    const issue: Issue = { code: "extra_official", message: "…" };
    expect(keys(survivingFields(whole, { ...whole }, [issue]))).toEqual(["source_urls"]);
  });

  it("shows a required field empty on BOTH sides — reads `same`, still blocks publish", () => {
    const blank = { ...whole, name: "" };
    const surviving = survivingFields(blank, { ...blank });
    expect(
      surviving.map((s) => [s.field.key, s.state, s.reason, s.error]),
    ).toEqual([
      ["name", "same", "error", "Required"],
      ["source_urls", "same", "context", null],
    ]);
  });

  it("prefers error over issue over diff when several apply", () => {
    const issue: Issue = {
      code: "duplicate_unique_role",
      message: "…",
      field: "office.name",
    };
    const surviving = survivingFields(
      whole,
      { ...whole, office: { ...whole.office, name: "" } },
      [issue],
    );
    expect(surviving.map((s) => [s.field.key, s.reason])).toEqual([
      ["office.name", "error"],
      ["source_urls", "context"],
    ]);
  });

  it("always surfaces source_urls, even when nothing about it changed", () => {
    const surviving = survivingFields(
      { ...whole, source_urls: ["a"] },
      { ...whole, source_urls: ["b", "c"] },
    );
    // `diff: false` means it is never *compared*, but `alwaysVisible` means it is
    // always *shown*: the sources are what a reviewer judges the other fields
    // from, so collapsing them away hides the evidence.
    expect(keys(surviving)).toEqual(["source_urls"]);
  });

  it("shows only the populated fields of an added person, not the whole schema", () => {
    const added = {
      id: "2",
      name: "Tom",
      office: {
        name: "Treasurer",
        division_ocdid: "ocd-division/country:us/state:nh/place:concord",
      },
      emails: ["t@x.gov"],
    };
    expect(keys(survivingFields(null, added))).toEqual([
      "name",
      "office.name",
      "office.division_ocdid",
      "emails",
          "source_urls",
    ]);
  });

  it("returns fields in schema order, not issue or edit order", () => {
    const surviving = survivingFields(whole, {
      ...whole,
      emails: [],
      name: "Marie",
    });
    expect(keys(surviving)).toEqual(["name", "emails", "source_urls"]);
  });
});

describe("fieldError — phones", () => {
  const phones = { key: "phones", label: "Phone", type: "multi" } as const;

  it("accepts every layout the backend canonicalises", () => {
    for (const value of [
      "(603) 968-4432",
      "603-968-4432",
      "6039684432",
      "+1 603 968 4432",
      "(603) 968-4432 ext. 12",
    ]) {
      expect(fieldError(phones, { phones: [value] })).toBeNull();
    }
  });

  it("flags what the backend would certainly reject, before Publish does", () => {
    expect(fieldError(phones, { phones: ["555-1234"] })).toMatch(/10-digit/);
  });

  it("ignores blanks — an empty row is not an error", () => {
    expect(fieldError(phones, { phones: ["", "  "] })).toBeNull();
  });
});
