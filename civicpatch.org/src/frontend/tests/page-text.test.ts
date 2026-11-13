import { describe, it, expect } from "vitest";
import { tidyLines } from "../components/source-content/page-text.js";

describe("tidyLines", () => {
  it("collapses runs of spaces and tabs inside a line", () => {
    expect(tidyLines("Jennifer   Forsyth,\tTreasurer")).toBe("Jennifer Forsyth, Treasurer");
  });

  it("keeps one blank line between blocks, never more", () => {
    expect(tidyLines("Treasurer\n\n\n\n  \nStaff")).toBe("Treasurer\n\nStaff");
  });

  it("drops blank lines at the start and end", () => {
    expect(tidyLines("\n\n  Board of Commissioners  \n\n")).toBe("Board of Commissioners");
  });
});
