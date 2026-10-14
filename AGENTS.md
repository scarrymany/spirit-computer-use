# Development

Use Windows PowerShell and Python. Preserve the Windows 11-only scope.

- Keep native APIs inside the isolated desktop/overlay workers.
- MCP stdout must contain only protocol messages.
- Do not retry desktop mutations after unknown outcomes.
- Never weaken window identity, snapshot, foreground or emergency-stop checks to
  make a test pass. Add a test for a reproducible defect.
- Keep third-party attribution when adapting code.
- Run Ruff and the affected pytest tests. Desktop tests need an unlocked desktop
  and explicitly opt in with SPIRIT_DESKTOP_TEST=1; they use the disposable fixture.
- Distinguish protocol/config compatibility from end-to-end tests in client apps.
- Do not commit artifacts, local environments, screenshots of user applications,
  credentials or generated configuration containing machine-specific paths.
