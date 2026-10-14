# Validation

Tests use local HTTP pages, an unpacked MV3 extension and a shared broker on an ephemeral
loopback port. Playwright is a test dependency only; production input goes through CDP.
The pinned test browser is Chrome for Testing 155.0.8059.79. Its archive digest is checked
by scripts/install-test-browser.ps1 before extraction.

Coverage includes background screenshots and input, CSS pixels at devicePixelRatio 2,
AX refs, same-process and cross-origin iframes, shadow DOM, stale-node refresh, covered
controls, moving targets, drag/scroll, Unicode, iframe password rejection, forms,
double/right clicks, keys, uploads with
an approval window, downloads, PDF/PNG, console/network metadata, navigation and cleanup.
The direct CDP test attaches to a disposable existing session and leaves it running after
disconnect. Security tests cover Origin/token checks and local-endpoint restrictions.
MCP tests initialize the stdio server and inspect its 26 browser/control tools.

Set SPIRIT_HEADED_TEST=1 for visible test windows. Set SPIRIT_CURSOR_TEST=1 to assert
unchanged OS cursor coordinates and foreground during the input sample; do not move the
mouse during that measurement. Ordinary runs still record these observations.

## Real Chrome check - 2026-10-14

The user loaded the unpacked extension into their ordinary Chrome profile. SPIRIT listed
nine existing tabs, read the 2048 page and captured its background screenshot at 2545x1305
CSS pixels. An ArrowLeft command changed the visible score from 0 to 4. The active tab,
foreground window and measured OS cursor position were unchanged. No game-state JS was
used. This verifies browser-local input, not a 30000-point game or universal website support.
Private tab URLs and screenshots are not included in the repository.

## Original reported failures

The earlier desktop client log showed an executable launch requested with a relative name,
a truncated process creation timestamp rejected by strict window identity checks, and a
click missing its required window argument. Version 0.2 removes that desktop API. Browser
calls use tab IDs, short element refs and a snapshot ID rather than process timestamps.

Client config parsing is tested; interactive operation inside every supported CLI is not.

The local full suite passed 19 tests. Ruff checks and formatting passed. A real MCP
client session listed nine tab resources, read a copied @ mention and exported tab files.
The extension reconnected after bridge restart and token rotation.
