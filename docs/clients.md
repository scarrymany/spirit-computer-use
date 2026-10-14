# Client connections

Run `scripts/install.ps1` from PowerShell first. It installs the engine in the
checkout's `.venv` and writes absolute-path connection snippets into
`artifacts/integrations/`. Keep that checkout at the same path. To move it,
recreate its virtual environment and regenerate configurations.

MCP is the common integration boundary. Client plugin formats are different;
there is no single native plugin manifest shared by all these products.

## Codex desktop / CLI

In the SPIRIT checkout:

```powershell
$pythonPath = (Resolve-Path '.venv/Scripts/python.exe').Path
codex mcp add spirit-computer-use -- $pythonPath -m spirit_computer_use serve
codex mcp get spirit-computer-use
```

Alternatively merge the generated `codex.toml` table into your Codex
`config.toml`. It sets a 40-second tool deadline, above the native-worker deadline.
Copy `skills/spirit-computer-use` to a skill directory supported by your Codex
installation, such as `~/.agents/skills/spirit-computer-use`.

[Official MCP documentation](https://developers.openai.com/codex/mcp)

## Claude Code CLI

```powershell
$pythonPath = (Resolve-Path '.venv/Scripts/python.exe').Path
claude mcp add --transport stdio --scope user spirit-computer-use -- $pythonPath -m spirit_computer_use serve
```

Copy the skill folder into `~/.claude/skills/` for global skill discovery.
Alternatively, this repository is a local Claude plugin: after installation,
run `claude --plugin-dir .` from the checkout. Its `.mcp.json` uses
`${CLAUDE_PLUGIN_ROOT}` to find the environment created by the installer.
Use either the plugin or the separate MCP registration to avoid duplicate servers.
Marketplace installation is not configured in this release.

[MCP](https://code.claude.com/docs/en/mcp) |
[Plugin manifest](https://code.claude.com/docs/en/plugins-reference)

## OpenCode

Merge `artifacts/integrations/opencode.json` into the project `opencode.json`
or your global `~/.config/opencode/opencode.json`. The entry uses `type: local`,
an argument array and a 40000 ms timeout. Copy the skill to
`~/.config/opencode/skills/spirit-computer-use` or the project's
`.opencode/skills/spirit-computer-use`.

[MCP](https://opencode.ai/docs/mcp-servers/) |
[Skills](https://opencode.ai/docs/skills/)

## Antigravity IDE / CLI

Merge `artifacts/integrations/antigravity.json` into
`~/.gemini/config/mcp_config.json` or the workspace's `.agents/mcp_config.json`.
The current official docs describe both products using the `mcpServers`
local command/args schema. Copy the skill into the workspace `.agents/skills/`
if your installed Antigravity version discovers that location; consult the
version's Skills settings when using a different discovery path.

[MCP](https://antigravity.google/docs/mcp) |
[Skills](https://antigravity.google/docs/skills)

## Cursor, VS Code and other MCP clients

The installer also produces `cursor.json`, `vscode.json` and `generic.json`.
Cursor/generic use `mcpServers`; VS Code uses `servers` and `type: stdio`.
Merge only the SPIRIT entry into the client's MCP settings.

Other agents work if they support local stdio MCP, JSON tool schemas and
PNG image content blocks. A text-only model can use UIA text, but cannot
understand screenshot pixels. Remote-only clients cannot launch a local desktop
process without their own bridge. SPIRIT does not expose a network listener.

## Validation levels

- The official Python MCP client is tested against the real stdio server,
  including initialization, discovery, calls and process shutdown.
- Configuration formats are generated and parsed in tests.
- Desktop automation is tested separately against a disposable WinForms app.
- Claude Code, OpenCode, Antigravity, Cursor and VS Code have not been exercised
  end-to-end with an agent model in this environment. Connection instructions
  are based on their published formats, not a claim of universal client certification.

Documentation checked on 2026-10-14. Host permissions and trust prompts remain
the client's responsibility; installation does not disable them.
