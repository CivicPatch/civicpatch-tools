import { describe, it, expect } from "vitest";
import { shortenIfUuid, usernameError } from "../components/username-utils.js";

describe("shortenIfUuid", () => {
  it("leaves a chosen username alone", () => {
    expect(shortenIfUuid("apple-witch")).toBe("apple-witch");
  });

  it("shortens a raw uuid to its trailing segment", () => {
    expect(shortenIfUuid("d9a966d4-286a-469e-a609-74e1a1f47dcb")).toBe("74e1a1f47dcb");
  });

  it("is not fooled by a uuid-shaped chosen name with different casing", () => {
    expect(shortenIfUuid("D9A966D4-286A-469E-A609-74E1A1F47DCB")).toBe("74E1A1F47DCB");
  });
});

describe("usernameError", () => {
  it("accepts letters, numbers, and '.', '_', '-'", () => {
    expect(usernameError("apple.witch_2-")).toBeNull();
  });

  it("rejects an empty or whitespace-only value", () => {
    expect(usernameError("")).toBe("Username is required");
    expect(usernameError("   ")).toBe("Username is required");
  });

  it("rejects a value over 50 characters", () => {
    expect(usernameError("a".repeat(51))).toBe("Username too long (max 50)");
  });

  it("accepts a value at exactly 50 characters", () => {
    expect(usernameError("a".repeat(50))).toBeNull();
  });

  it("rejects disallowed characters", () => {
    expect(usernameError("apple witch")).toBe(
      "Username may only contain letters, numbers, '.', '_', and '-'",
    );
    expect(usernameError("apple@witch")).toBe(
      "Username may only contain letters, numbers, '.', '_', and '-'",
    );
  });
});
