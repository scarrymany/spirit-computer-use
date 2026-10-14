# Client integration

The transport is MCP over stdio. All clients launch the same Python server:

```text
<absolute-path-to-python.exe> -m spirit_computer_use serve
```

`spirit config <client>` prints a configuration snippet. Merge it with existing settings;
do not overwrite unrelated servers. Paths containing spaces remain a single argument.
Allow at least 130 seconds per tool call because confirmation dialogs can wait 110 seconds.

| Client | Configuration output | Skill directory |
| --- | --- | --- |
| Codex CLI / app | `config codex`, TOML MCP entry | `~/.codex/skills/spirit-computer-use` |
| Claude Code / CLI | `config claude`, mcpServers JSON | `.claude/skills/spirit-computer-use` |
| Antigravity CLI (agy) | `config antigravity`, mcpServers JSON | `~/.gemini/antigravity-cli/skills/spirit-computer-use` |
| OpenCode | `config opencode`, local MCP JSON | Use the client's supported skill location |
| Cursor | `config cursor`, mcpServers JSON | Use MCP tools directly or configure its instructions |
| VS Code | `config vscode`, servers JSON | Use MCP tools directly |
| Other MCP clients | `config generic` | Optional; tools include descriptions |

On the tested agy installation, MCP configuration is `~/.gemini/config/mcp_config.json`.
Invoke `/spirit-computer-use` after restarting agy. For Codex use `$spirit-computer-use`.
Claude Code can also load the repository's `.claude-plugin` metadata through its plugin
workflow; this does not automatically install Python or the Chrome extension.

## Selecting tabs

The server publishes `spirit://tab/<id>` resources and tab-list change notifications.
Resource autocomplete is determined by the client. The extension popup lists/searches
existing tabs and copies `@spirit-tab:<id>` to paste into a prompt.

For clients whose @ picker lists files, ask the agent to run `browser_export_tabs` for
the current workspace. Select `.spirit/tabs/<id>.md`. The exported file contains a title,
URL and stable tab ID. It is a selection reference, not permission to act on the page.
Run export again to refresh titles and newly opened tabs. Closed-tab files may remain;
a stale ID is rejected rather than silently redirected.

## Compatibility claims

Configuration parsing and MCP protocol behavior are tested locally. This is not a claim
that each client's interactive UI has been tested end to end. Native composer extensions
are not part of MCP, so identical autocomplete UI across all clients is not promised.
