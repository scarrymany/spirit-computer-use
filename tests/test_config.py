import json

import pytest

from spirit_computer_use.config import CLIENTS, generate_config


@pytest.mark.parametrize("client", [client for client in CLIENTS if client != "codex"])
def test_config_keeps_executable_with_spaces_as_single_argument(client):
    result = json.loads(generate_config(client, "C:/Program Files/SPIRIT/python.exe"))
    if client == "opencode":
        entry = result["mcp"]["spirit-computer-use"]
        assert entry["command"][0].endswith("python.exe")
        assert len(entry["command"]) == 4
    else:
        entry = result.get("mcpServers", result.get("servers"))["spirit-computer-use"]
        assert entry["command"].endswith("python.exe")
        assert entry["args"] == ["-m", "spirit_computer_use", "serve"]


def test_codex_config_is_valid_toml():
    import tomli

    data = tomli.loads(generate_config("codex", "C:/Program Files/SPIRIT/python.exe"))
    entry = data["mcp_servers"]["spirit-computer-use"]
    assert entry["args"] == ["-m", "spirit_computer_use", "serve"]
    assert entry["tool_timeout_sec"] > 25


def test_unknown_client_rejected():
    with pytest.raises(ValueError):
        generate_config("unknown")
