# Validation record

Local validation date: **2026-10-14**.

Environment: Windows 11 x64 build 26200, Python 3.10.11, MCP SDK 1.30.0,
windows-capture 2.0.1, pywinauto 0.6.9, Pillow 12.3.0.

## Completed

- **33 pytest tests passed**, including the opt-in desktop tests, in 8.68 seconds.
- Ruff lint and formatting checks.
- SKILL.md validation with the Codex skill-creator validator.
- PowerShell installer: environment setup, dependency installation, runtime
  diagnostics and generation of seven parseable client configuration files.
- `pip check` reports no broken requirements.
- Source distribution and wheel build. A wheel was installed into a separate
  clean virtual environment and its `doctor` command successfully started the engine.
- Archive inspection: no local environments, research clones, generated configuration
  or compiled fixture outputs in the source distribution; adapted-code license in wheel.
- Real overlay screenshot visually inspected. The README image was captured from
  the disposable test application, not from a user's application.

## Behaviors exercised

- Real MCP initialize, tool listing, tool calls, error results and clean shutdown.
- Actual PNG image blocks and UIA text through MCP stdio.
- HWND enumeration, identity refresh and foreground activation.
- WGC screenshot capture with dimension checks.
- UIA element discovery, focus, selected text and editable values.
- Mouse clicks, Unicode text including Cyrillic/CJK/emoji, Ctrl+A, UIA toggle,
  drag and vertical scroll, verified by the target application's resulting state.
- Rejection of consumed, expired, moved-window and mismatched-identity snapshots.
- Failed focus and failed capture invalidate earlier observations.
- Emergency-stop blocking, explicit resume, worker deadlines and subprocess reaping.
- Input ABI size, chord cleanup and recorded-input cleanup after interruption.
- Configuration structure and executable paths containing spaces.

## Not established by these checks

- End-to-end model-driven operation in every supported MCP host.
- Every third-party application, browser engine or GPU surface.
- Mixed-DPI multimonitor configurations, HDR, RDP reconnects, Windows ARM64,
  secure/elevated desktops or full-screen games.
- Pixel-identical appearance or complete API parity with the OpenAI plugin.
- Reliability benchmarks over long-running sessions or a third-party security audit.

The GitHub workflow runs the non-desktop suite and package build on Windows with
Python 3.10, 3.12 and 3.13. Its results are separate from the local desktop evidence
and can be inspected under the repository's Actions tab.
