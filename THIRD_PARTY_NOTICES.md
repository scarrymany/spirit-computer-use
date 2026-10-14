# Third-party software and research

SPIRIT is an independent implementation. It does not redistribute OpenAI Computer
Use binaries, private protocols or source code. It is not affiliated with OpenAI,
Anthropic, Google, CursorTouch or Microsoft.

## Adapted code

The dual-thread focus attachment in `src/spirit_computer_use/native.py:activate`
is adapted from `Desktop.bring_window_to_top` in
[CursorTouch/Windows-MCP](https://github.com/CursorTouch/Windows-MCP/blob/8573729804c8cc5dd8698a85f01003dc8c58fbe0/src/windows_mcp/desktop/service.py).
Reviewed upstream revision: `8573729804c8cc5dd8698a85f01003dc8c58fbe0`.
SPIRIT uses ctypes bindings, verifies the selected window identity and foreground,
and detaches in reverse order. The upstream license follows.

MIT License

Copyright (c) 2025 JEOMON GEORGE

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Runtime dependencies

Installed separately by pip; each distribution carries its own license:

| Dependency | Purpose | Upstream |
| --- | --- | --- |
| windows-capture | GPU window capture by HWND | [Repository](https://github.com/NiiightmareXD/windows-capture) |
| pywinauto | Windows UI Automation wrappers | [Repository](https://github.com/pywinauto/pywinauto) |
| mcp | Official MCP Python SDK, stable 1.x API | [Repository](https://github.com/modelcontextprotocol/python-sdk) |
| Pillow | PNG encoding and preview capture | [Repository](https://github.com/python-pillow/Pillow) |
| Pydantic | Tool argument validation | [Repository](https://github.com/pydantic/pydantic) |
| psutil | Process identity and creation times | [Repository](https://github.com/giampaolo/psutil) |

## Research references

Microsoft UFO was inspected at revision `a795552d976c4c019d7c2f778a0effb5cef7de6b`
for UIA focus and controller design. No UFO code is included.

The current Windows-MCP application is not vendored: its broader tool surface,
Python 3.14 runtime and dependencies are outside this release's scope. SPIRIT
reuses a focused MIT-licensed technique and established libraries instead.
