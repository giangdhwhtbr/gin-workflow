# Design: Reuse launcher installation logic

Date: 2026-10-05
Status: confirmed in conversation on 2026-10-05
Epic: gin-workflow-f7g
Bead and workflow ID: gin-workflow-f7g.1

## Goal and Scope

Remove duplicated launcher installation logic for gin-workflow and gin-qa while preserving existing behavior. Scope is install.sh, install.ps1, and relevant coverage in tests/install_smoke_test.sh and tests/install_smoke_test.ps1. Other audit findings have separate scopes. Line-count savings are an estimate, not an acceptance threshold.

## Architecture

Use one shared launcher installation function in each shell, taking the launcher name and version. Update the existing dispatch sites to supply the two supported launchers. Keep a small explicit branch for plugin-specific content and warnings; do not introduce a registry, callbacks, configuration format, dependency, or cross-shell abstraction.

gin-workflow installs workflow_core, rules, and templates. gin-qa installs gin_qa and templates. Preserve existing source paths, versioned installation paths, executable names, permissions, and platform-specific link or shim formats. Reuse the existing managed-launcher ownership checks with the appropriate launcher name.

## Data Flow and Error Handling

Preserve each launcher's current sequence: derive paths, validate any existing launcher, emit the gin-qa dependency warning when applicable, handle dry-run, copy files, publish the launcher, and emit completion output. The gin-workflow PATH warning remains after successful installation; gin-qa does not acquire that warning.

Keep existing dry-run messages and launcher-write behavior, error propagation, upgrade eligibility, and refusal to replace foreign or malformed launchers. Preserve Bash symlink behavior and PowerShell temporary-file replacement with cleanup in finally. This refactor does not change the broader installer's existing dry-run behavior or add transactional guarantees to package copying.

## Testing

Use the existing Bash and PowerShell installer smoke tests. Preserve coverage of installation, dry-run, installed CLI behavior, managed upgrades, and refusal to overwrite foreign or malformed launchers. Extend the existing suites where equivalent gin-qa upgrade and collision coverage is missing; confirm rejected installation leaves the existing launcher intact.

Run bash tests/install_smoke_test.sh and pwsh -NoProfile -File tests/install_smoke_test.ps1 in suitable environments. Report unavailable platform validation explicitly rather than claiming it passed. Verify the final diff and obtain independent review before closing the bead.

## Acceptance Criteria

- Each shell has one shared installation flow for both existing launchers.
- Installed content, messages, warning conditions and ordering, dry-run behavior, ownership checks, and error handling remain unchanged.
- No new runtime dependencies or generalized extension mechanisms are introduced.
- Relevant smoke tests pass on the validated platforms, with any unavailable validation explicitly recorded; independent review approves the change.

## Alternatives and Confirmation

The alternative was extracting smaller helpers while retaining both installation flows; it would retain more duplication. The user chose the shared-function approach and explicitly confirmed the architecture, behavior preservation, and test scope in conversation. This document records that confirmed design. Planning and implementation are separate stages.
