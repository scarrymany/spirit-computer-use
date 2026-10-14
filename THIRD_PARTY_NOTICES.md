# Third-party notices

SPIRIT Browser is MIT licensed. Dependencies retain their own licenses:

- MCP Python SDK: MIT
- Pydantic: MIT
- websockets: BSD-3-Clause
- Pillow: HPND
- Playwright (test dependency): Apache-2.0

The browser implementation and SVG assets in this repository are original. The following
projects were examined as architecture references; their source is not vendored:

| Reference | License | Design relevance |
| --- | --- | --- |
| [Chrome DevTools MCP](https://github.com/ChromeDevTools/chrome-devtools-mcp) | Apache-2.0 | Existing-session consent connection |
| [Playwright MCP](https://github.com/microsoft/playwright-mcp) | Apache-2.0 | Extension-based existing-profile access |
| [playwriter](https://github.com/remorses/playwriter) | MIT | Extension-origin bridge boundary |
| [Pagewright](https://github.com/zamansheikh/browser-mcp) | MIT | Separate extension/agent connection trust |
| [RunBrowser](https://github.com/termio-sh/browser) | MIT | CDP over an extension bridge |
| [ghost-cursor](https://github.com/Xetera/ghost-cursor) | MIT | Pointer trajectory reference; SPIRIT uses its own cubic curve |

Parithosh-Varma/browser-mcp was examined conceptually. No code was copied because an
explicit reuse license was not identified during the review.

Chrome and Chromium are Google projects. Chrome for Testing is downloaded separately for
local tests; browser binaries are not distributed with SPIRIT. SPIRIT is not affiliated
with Google, Anthropic, Microsoft or OpenAI.
