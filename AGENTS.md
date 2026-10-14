# Development

Use Windows PowerShell and Python. SPIRIT controls Chrome tabs on Windows 11.

- Keep browser input inside CDP. Do not add desktop input APIs.
- MCP stdout contains protocol messages only.
- Never retry mutations with unknown outcomes. Observe first.
- Preserve snapshot, navigation, origin, session ownership and stop checks.
- Keep third-party attribution when adapting code.
- Run Ruff and affected pytest tests. Browser tests use a disposable Chrome for Testing profile.
- Distinguish MCP/config compatibility from end-to-end tests inside client products.
- Never commit credentials, connection.json, exported user tabs or private screenshots.
