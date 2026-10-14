# Architecture

```text
MCP client / agent
      |
      | JSON-RPC stdio (text + PNG image content)
      v
Python MCP server ---- Controller deadlines / input ledger
                            |
                            +-- Spawned desktop worker
                            |     Windows Graphics Capture (HWND)
                            |     UI Automation (COM)
                            |     SendInput / foreground validation
                            |     Bounded snapshot cache
                            |
                            +-- Spawned overlay and stop monitor
                                  Non-activating transparent Tk window
                                  Purple outline, cyan cursor ring
                                  Pause / Ctrl+Alt+Escape latch
```

## Process ownership

Desktop calls are serialized inside each controller and across SPIRIT clients by
a named Windows mutex. Native calls live outside the MCP event loop. A native
timeout terminates the worker, invalidates its snapshots, latches input stop and
reports an unknown outcome. It never retries a write automatically.

Workers launch through the base interpreter's `pythonw.exe` using Python's
spawn context. Using the virtual-environment redirector for pythonw inserts an
extra process and breaks duplicated Windows synchronization handles. The spawn
preparation restores the environment's import paths, and pywin32's documented
bootstrap module restores its DLL search directory. Native libraries are imported
only inside the worker, keeping their initialization under the operation deadline.

MCP stdout carries protocol messages only. Worker output is separate. Shutdown
closes the worker connection, stops the overlay, joins processes and closes the
overlay queue. The overlay also notices a dead parent. A shared ledger records
only SPIRIT's held keys/buttons so forced worker cleanup can release those inputs.
There is no Windows service or persistent background startup task.

## Observation identity

A `Window` includes HWND, PID, process creation time, executable path and title.
Before each operation the worker checks that the process identity still matches.
Snapshots add physical DWM bounds, a random id, timestamp and UIA element references.
The latest observation supersedes earlier observations of the same window. The
cache holds at most 16 snapshots with a 120-second lifetime.

Input requires an unexpired matching snapshot, unchanged bounds, successful
activation and a foreground check. Pointer actions additionally hit-test the
coordinate against the selected root HWND. Keys/buttons are released in cleanup.
These checks limit common stale-coordinate mistakes; they cannot prevent an app
from changing content between observation and input. The agent must verify outcomes.

## Images and accessibility

WGC captures the selected HWND, without rescaling. Its size must match DWM bounds;
otherwise the operation rejects the observation rather than guessing a scale.
The original image dimensions and window origin accompany every screenshot.

UIA traversal is limited by time, element count and depth. Partial results identify
truncation and provider errors. A hung individual COM call is bounded by the outer
worker deadline. Password values are omitted, and password entry is not automated.

Separate transient windows are separately selectable. Automatic popup composition,
browser DOM extraction and an exact `@oai/sky` API shim are outside version 0.1.0.

## Open-source choices

Windows-MCP and Microsoft UFO were inspected as reference implementations. The
dual-thread activation strategy from Windows-MCP was adapted under MIT; see the
exact revision and license in `THIRD_PARTY_NOTICES.md`. Its full agent toolset is
not bundled. Capture, COM wrappers and MCP use maintained third-party packages.

The engine does not invoke an LLM, charge for inference, send telemetry or open a
network port. MCP clients control their own inference provider and permissions.
