from __future__ import annotations

import json
import sys
from pathlib import Path

CLIENTS = ("codex", "claude", "opencode", "antigravity", "cursor", "vscode", "generic")
SERVER_NAME = "spirit-computer-use"


def generate_config(client: str, executable: str | None = None) -> str:
    command = str(Path(executable or sys.executable).resolve())
    args = ["-m", "spirit_computer_use", "serve"]
    if client == "codex":
        return (
            f"[mcp_servers.{SERVER_NAME}]\ncommand = {json.dumps(command)}\n"
            f"args = {json.dumps(args)}\nstartup_timeout_sec = 30\ntool_timeout_sec = 40\n"
        )
    if client == "opencode":
        value = {
            "$schema": "https://opencode.ai/config.json",
            "mcp": {
                SERVER_NAME: {
                    "type": "local",
                    "command": [command, *args],
                    "enabled": True,
                    "timeout": 40000,
                }
            },
        }
    elif client == "vscode":
        value = {"servers": {SERVER_NAME: {"type": "stdio", "command": command, "args": args}}}
    elif client in CLIENTS:
        value = {"mcpServers": {SERVER_NAME: {"command": command, "args": args}}}
    else:
        raise ValueError(f"Unknown client: {client}")
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"
