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

  it("names the variable, not the key, for every agent that has a shell or editor", () => {
    for (const setup of agentSetups(ORIGIN, KEY).filter((candidate) => candidate.agent !== "Claude.ai")) {
      expect(textOf(setup)).not.toContain(KEY);
    }
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

  it("gives ChatGPT the same /mcp every agent uses", () => {
    expect(mcpUrl(ORIGIN)).toBe("https://civicpatch.org/mcp");
  });
});
