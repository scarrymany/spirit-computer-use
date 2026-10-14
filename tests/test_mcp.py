import asyncio
import json
import sys
from datetime import timedelta

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def test_stdio_handshake_tools_and_status():
    async def run():
        parameters = StdioServerParameters(
            command=sys.executable, args=["-m", "spirit_computer_use", "serve"]
        )
        async with stdio_client(parameters) as (reader, writer):
            async with ClientSession(
                reader, writer, read_timeout_seconds=timedelta(seconds=15)
            ) as session:
                info = await session.initialize()
                assert info.serverInfo.name == "SPIRIT Browser"
                assert info.capabilities.resources.listChanged is True
                tools = (await session.list_tools()).tools
                assert len(tools) == 27
                assert all(
                    t.name not in {"list_windows", "launch_app", "get_window_state"} for t in tools
                )
                status = await session.call_tool("status", {})
                assert not status.isError
                assert json.loads(status.content[0].text)["desktop_control"] is False
                invalid = await session.call_tool(
                    "browser_click", {"tab": "1", "snapshot_id": "missing", "x": -1}
                )
                assert invalid.isError
                stopped = await session.call_tool("emergency_stop", {})
                assert not stopped.isError
                result = await session.call_tool("status", {})
                assert json.loads(result.content[0].text)["emergency_stopped"]
                assert not (await session.call_tool("resume", {})).isError

    asyncio.run(run())
