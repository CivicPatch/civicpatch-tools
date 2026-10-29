import { describe, it, expect } from "vitest";
import { agentSetups, exportLine, mcpUrl, type AgentSetup } from "../pages/settings-page/api-key-commands.js";

const ORIGIN = "https://civicpatch.org";
const KEY = "cp_abc123";

const setupFor = (agent: string) => {
  const setup = agentSetups(ORIGIN, KEY).find((candidate) => candidate.agent === agent);
  if (!setup) throw new Error(`no setup for ${agent}`);
  return setup;
};

const textOf = (setup: AgentSetup) => setup.fields.map((field) => field.value).join("\n");

describe("api key commands", () => {
  it("puts the key in the export line, and only there", () => {
    expect(exportLine(KEY)).toBe("export CIVICPATCH_API_KEY=cp_abc123");
  });

  it("points every agent at this site's /mcp", () => {
    for (const setup of agentSetups(ORIGIN, KEY)) {
      expect(textOf(setup)).toContain("https://civicpatch.org/mcp");
    }
  });

  it("puts the key only in the shell profile line and Claude.ai's header box", () => {
    const keyHolders = new Set(["Shell profile", "Request header value"]);
    for (const setup of agentSetups(ORIGIN, KEY)) {
      for (const field of setup.fields.filter((candidate) => !keyHolders.has(candidate.label))) {
        expect(field.value).not.toContain(KEY);
      }
    }
    expect(setupFor("Claude Code").fields[0]).toEqual({ label: "Shell profile", value: exportLine(KEY) });
  });

  it("without a key, shows where one goes instead of filling it in", () => {
    const setups = agentSetups(ORIGIN, null);

    expect(setups.flatMap((setup) => setup.fields.map((field) => field.label))).not.toContain("Shell profile");
    expect(setups.find((setup) => setup.agent === "Claude Code")?.where).toContain("create one above");
    expect(setups.find((setup) => setup.agent === "Claude.ai")?.fields.map((field) => field.label)).toEqual([
      "Name",
      "URL",
      "Request header name",
    ]);
  });

  it("uses each agent's own syntax for the key", () => {
    expect(textOf(setupFor("Claude Code"))).toContain("'Authorization: Bearer ${CIVICPATCH_API_KEY}'");
    expect(textOf(setupFor("Codex CLI"))).toContain("--bearer-token-env-var CIVICPATCH_API_KEY");
    expect(textOf(setupFor("VS Code"))).toContain("Bearer ${input:civicpatch-api-key}");
  });

  it("gives Claude.ai one field per box in its dialog, the header value holding the key itself", () => {
    const fields = Object.fromEntries(setupFor("Claude.ai").fields.map((field) => [field.label, field.value]));

    expect(fields).toEqual({
      Name: "civicpatch",
      URL: "https://civicpatch.org/mcp",
      "Request header name": "Authorization",
      "Request header value": `Bearer ${KEY}`,
    });
  });

  it("lists ChatGPT first, with the same /mcp, its steps and no key", () => {
    const [first] = agentSetups(ORIGIN, KEY);

    expect(mcpUrl(ORIGIN)).toBe("https://civicpatch.org/mcp");
    expect(first.agent).toBe("ChatGPT");
    expect(first.fields).toEqual([{ label: "Server URL", value: "https://civicpatch.org/mcp" }]);
    expect(first.steps.length).toBeGreaterThan(0);
  });
});
