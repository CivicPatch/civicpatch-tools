const API_KEY_VARIABLE = "CIVICPATCH_API_KEY";
const SERVER_NAME = "civicpatch";

// One value to paste somewhere, so a dialog with several boxes gets one field per box.
export type SetupField = {
  label: string;
  value: string;
};

export type AgentSetup = {
  agent: string;
  where: string;
  fields: SetupField[];
  steps: string[];
};

export const exportLine = (key: string) => `export ${API_KEY_VARIABLE}=${key}`;

export const mcpUrl = (origin: string) => `${origin}/mcp`;

const json = (value: object) => JSON.stringify(value, null, 2);

// ChatGPT accepts only OAuth: it registers itself and sends the user to our consent page, so no key.
function chatGptSetup(url: string): AgentSetup {
  return {
    agent: "ChatGPT",
    where: "ChatGPT signs in as you, so it needs no key",
    fields: [{ label: "Server URL", value: url }],
    steps: [
      "Open chatgpt.com/plugins, then + and Add custom MCP server",
      "Give it a name and paste the Server URL above",
      "Authentication: OAuth, with client id and secret left empty",
      "Tick the warning, create it, then install it: ChatGPT opens civicpatch to approve it",
    ],
  };
}

// The key only ever goes in the shell profile; the command names the variable.
function shellSetup(agent: string, command: SetupField, key: string | null): AgentSetup {
  if (!key) {
    return {
      agent,
      where: `Put an agent key (create one above) in ${API_KEY_VARIABLE} in your shell profile, not in a chat, then`,
      fields: [command],
      steps: [],
    };
  }
  return {
    agent,
    where: "Add the first line to your shell profile, not to a chat, then",
    fields: [{ label: "Shell profile", value: exportLine(key) }, command],
    steps: [],
  };
}

// A browser app has no shell to read a variable from, so its header holds the key itself.
function claudeAiSetup(url: string, key: string | null): AgentSetup {
  const boxes = [
    { label: "Name", value: SERVER_NAME },
    { label: "URL", value: url },
    { label: "Request header name", value: "Authorization" },
  ];
  const where = "Settings → Connectors → Add custom connector. Choose no sign in, then fill in each box";
  if (!key) {
    return { agent: "Claude.ai", where: `${where}; the header value is Bearer and an agent key (create one above)`, fields: boxes, steps: [] };
  }
  return { agent: "Claude.ai", where, fields: [...boxes, { label: "Request header value", value: `Bearer ${key}` }], steps: [] };
}

/** `key` is a just-created agent key, filled in where a setup needs it; null shows where one goes. */
export function agentSetups(origin: string, key: string | null): AgentSetup[] {
  const url = mcpUrl(origin);
  return [
    chatGptSetup(url),
    claudeAiSetup(url, key),
    shellSetup(
      "Claude Code",
      {
        label: "Command",
        value: `claude mcp add --scope user --transport http ${SERVER_NAME} ${url} --header 'Authorization: Bearer \${${API_KEY_VARIABLE}}'`,
      },
      key,
    ),
    shellSetup(
      "Codex CLI",
      { label: "Command", value: `codex mcp add ${SERVER_NAME} --url ${url} --bearer-token-env-var ${API_KEY_VARIABLE}` },
      key,
    ),
    shellSetup(
      "Gemini CLI",
      {
        label: "Add to ~/.gemini/settings.json",
        value: json({
          mcpServers: {
            [SERVER_NAME]: { httpUrl: url, headers: { Authorization: `Bearer \${${API_KEY_VARIABLE}}` } },
          },
        }),
      },
      key,
    ),
    // Cursor: unverified; its `${env:…}` in remote-server headers was reported broken in one release.
    // {
    //   agent: "Cursor",
    //   where: "Add to ~/.cursor/mcp.json",
    //   fields: [{ label: "Settings", value: json({
    //     mcpServers: { [SERVER_NAME]: { url, headers: { Authorization: `Bearer \${env:${API_KEY_VARIABLE}}` } } },
    //   }) }],
    // },
    {
      agent: "VS Code",
      where: "Add to .vscode/mcp.json; VS Code asks for the key once and stores it",
      fields: [
        {
          label: "Settings",
          value: json({
            servers: {
              [SERVER_NAME]: {
                type: "http",
                url,
                headers: { Authorization: `Bearer \${input:${SERVER_NAME}-api-key}` },
              },
            },
            inputs: [
              {
                type: "promptString",
                id: `${SERVER_NAME}-api-key`,
                description: "civicpatch API key",
                password: true,
              },
            ],
          }),
        },
      ],
      steps: [],
    },
  ];
}
