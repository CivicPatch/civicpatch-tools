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
};

export const exportLine = (key: string) => `export ${API_KEY_VARIABLE}=${key}`;

export const mcpUrl = (origin: string) => `${origin}/mcp`;

// ChatGPT accepts only OAuth: it registers itself and sends the user to our consent page, so no key.
export const CHATGPT_STEPS = [
  "Open chatgpt.com/plugins, then + and Add custom MCP server",
  "Give it a name and paste the Server URL above",
  "Authentication: OAuth, with client id and secret left empty",
  "Tick the warning, create it, then install it: ChatGPT opens civicpatch to approve it",
];

const json = (value: object) => JSON.stringify(value, null, 2);

// Every setup names the variable, never the key, except Claude.ai: a browser app has no shell
// to read one from, so its header holds the key itself, stored by Claude.ai.
export function agentSetups(origin: string, key: string): AgentSetup[] {
  const url = mcpUrl(origin);
  return [
    {
      agent: "Claude Code",
      where: "Run in your terminal",
      fields: [
        {
          label: "Command",
          value: `claude mcp add --scope user --transport http ${SERVER_NAME} ${url} --header 'Authorization: Bearer \${${API_KEY_VARIABLE}}'`,
        },
      ],
    },
    {
      agent: "Codex CLI",
      where: "Run in your terminal",
      fields: [{ label: "Command", value: `codex mcp add ${SERVER_NAME} --url ${url} --bearer-token-env-var ${API_KEY_VARIABLE}` }],
    },
    {
      agent: "Gemini CLI",
      where: "Add to ~/.gemini/settings.json",
      fields: [
        {
          label: "Settings",
          value: json({
            mcpServers: {
              [SERVER_NAME]: { httpUrl: url, headers: { Authorization: `Bearer \${${API_KEY_VARIABLE}}` } },
            },
          }),
        },
      ],
    },
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
    },
    {
      agent: "Claude.ai",
      where: "Settings → Connectors → Add custom connector. Choose no sign in, then fill in each box",
      fields: [
        { label: "Name", value: SERVER_NAME },
        { label: "URL", value: url },
        { label: "Request header name", value: "Authorization" },
        { label: "Request header value", value: `Bearer ${key}` },
      ],
    },
  ];
}
