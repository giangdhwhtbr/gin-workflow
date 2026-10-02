---
id: python
tier: language
applies_to: ["**/*.py"]
detect: {files_exist: [pyproject.toml, requirements.txt]}
tool_checks:
  - id: ruff
    check: {pyproject_tool: tool.ruff}
    suggest: |
      [tool.ruff.lint]
      select = ["E", "F", "I", "B", "UP", "BLE"]
  - id: mypy
    check: {pyproject_tool: tool.mypy}
    suggest: |
      [tool.mypy]
      strict = true
---
- [critical] `typed-public`: Annotate every public function signature; keep `Any` inside boundary adapters.
- [high] `structured-data`: Pass structured data as dataclasses or Pydantic models, not loose dicts between modules.
- [high] `io-at-edges`: Keep network, disk, and env access at the edges; core functions take and return values.
- `no-module-state`: Do not keep mutable state at module level; pass dependencies explicitly.
- `local-fixtures`: Keep pytest fixtures beside their tests; move one to `conftest.py` only when shared.

## Why
- `typed-public`: Signatures are the contract callers and type checkers rely on.
- `io-at-edges`: Pure cores are testable without mocks.
