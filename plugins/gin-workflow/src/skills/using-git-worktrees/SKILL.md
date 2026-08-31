---
name: using-git-worktrees
description: Self-contained — create and manage isolated git worktree workspaces with provider-backed safety constraints.
---

# Using Git Worktrees

## Overview

Ensure work happens in an isolated workspace. Create, isolate, inspect, and clean workspaces only through the configured workspace capability. Fall back to manual git worktrees only when no native capability is available.

**Core principle:** Detect existing isolation first. Then use native tools. Then fall back to git. Never fight the harness. Require unique branch/workspace identities and enforce the configured filesystem safety boundary before mutation.

## Required Inputs

- Resolved `EffectiveConfig`
- `ArtifactRegistry`
- Stage-specific `ContextManifest`
- Native-harness `ApprovalDecision`

## Step 0: Detect Existing Isolation

**Before creating anything, check if you are already in an isolated workspace.**

```bash
GIT_DIR=$(cd "$(git rev-parse --git-dir)" 2>/dev/null && pwd -P)
GIT_COMMON=$(cd "$(git rev-parse --git-common-dir)" 2>/dev/null && pwd -P)
BRANCH=$(git branch --show-current)
```

**Submodule guard:** `GIT_DIR != GIT_COMMON` is also true inside git submodules. Before concluding "already in a worktree," verify you are not in a submodule:

```bash
# If this returns a path, you're in a submodule, not a worktree — treat as normal repo
git rev-parse --show-superproject-working-tree 2>/dev/null
```

**If `GIT_DIR != GIT_COMMON` (and not a submodule):** You are already in a linked worktree. Skip to Step 2 (Project Setup). Do NOT create another worktree.

Report with branch state:
- On a branch: "Already in isolated workspace at `<path>` on branch `<name>`."
- Detached HEAD: "Already in isolated workspace at `<path>` (detached HEAD, externally managed). Branch creation needed at finish time."

**If `GIT_DIR == GIT_COMMON` (or in a submodule):** You are in a normal repo checkout.

Isolation disablement or current-branch execution requires `approval-manager` authorization plus durable audit evidence. Ask for consent before creating a worktree if preference is not already given:

> "Would you like me to set up an isolated worktree? It protects your current branch from changes."

Honor any existing declared preference without asking. If the user declines consent, acquire `approval-manager` authorization, work in place, and skip to Step 2.

## Step 1: Create Isolated Workspace

**You have two mechanisms. Try them in this order.**

### 1a. Native Worktree Tools (preferred)

The user has asked for an isolated workspace (Step 0 consent). Do you already have a configured workspace capability to create a worktree (e.g., an explicit native tool for worktree management)? If you do, use it and skip to Step 2.

Native tools handle directory placement, branch creation, and cleanup automatically. Using `git worktree add` when you have a native tool creates phantom state your harness can't see or manage.

Only proceed to Step 1b if you have no native worktree capability available.

### 1b. Git Worktree Fallback

**Only use this if Step 1a does not apply** — you have no native worktree tool available. Create a worktree manually using git.

#### Directory Selection

Resolve the workspace root from `ArtifactRegistry["worktrees"]` and use one explicit track identity; reject wildcards or unresolved paths. 

#### Safety Verification

**MUST verify the directory is ignored before creating worktree:**

```bash
git check-ignore -q "$WORKSPACE_ROOT" 2>/dev/null
```

**If NOT ignored:** Add to `.gitignore` (do not commit `.gitignore` without explicit user authorization per `AGENTS.md`), then proceed.

**Why critical:** Prevents accidentally committing worktree contents to repository. Require unique branch/workspace identities and enforce the configured filesystem safety boundary before mutation.

#### Create the Worktree

1. Invoke the configured `WorkspaceProvider` capability to create and register the workspace (`workspace.create`).
2. Discover workspace paths and branch names through workspace-provider records. Require unique branch/workspace identities and enforce the configured filesystem safety boundary.
3. Switch working directory to the created workspace.

Treat workspace paths and branch names as supplemental runtime metadata. Durable status and completion remain owned by the task-tracking capability.

**Sandbox fallback:** If `git worktree add` fails with a permission error (sandbox denial), inform the user the sandbox blocked worktree creation and you're working in the current directory instead. Acquire necessary approval, then run setup and baseline tests in place.

## Step 2: Project Setup

Auto-detect and run appropriate setup:

```bash
# Node.js — respect project lockfile & package manager
if [ -f pnpm-lock.yaml ]; then pnpm install;
elif [ -f yarn.lock ]; then yarn install;
elif [ -f package-lock.json ]; then npm ci;
elif [ -f package.json ]; then npm install; fi

# Rust
if [ -f Cargo.toml ]; then cargo build; fi

# Python
if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
if [ -f pyproject.toml ]; then poetry install; fi

# Go
if [ -f go.mod ]; then go mod download; fi
```

## Step 3: Verify Clean Baseline

Run tests to ensure workspace starts clean:

```bash
# Use project-appropriate command
npm test / cargo test / pytest / go test ./...
```

**If tests fail:** Report failures, ask whether to proceed or investigate.

**If tests pass:** Report ready.

### Report

```
Worktree ready at <full-path>
Tests passing (<N> tests, 0 failures)
Ready to implement <feature-name>
```

## Quick Reference

| Situation | Action |
|-----------|--------|
| Already in linked worktree | Skip creation (Step 0) |
| In a submodule | Treat as normal repo (Step 0 guard) |
| Native worktree tool available | Use it (Step 1a) |
| No native tool | Git worktree fallback (Step 1b) |
| Directory not ignored | Add to .gitignore (commit only if authorized) |
| Permission error on create | Sandbox fallback, work in place (with approval) |
| Tests fail during baseline | Report failures + ask |
| No package.json/Cargo.toml | Skip dependency install |

## Common Mistakes

### Fighting the harness

- **Problem:** Using `git worktree add` when the platform already provides isolation capability
- **Fix:** Step 0 detects existing isolation. Step 1a defers to native tools.

### Skipping detection

- **Problem:** Creating a nested worktree inside an existing one
- **Fix:** Always run Step 0 before creating anything

### Skipping ignore verification

- **Problem:** Worktree contents get tracked, pollute git status
- **Fix:** Always use `git check-ignore` before creating a project-local worktree

### Assuming directory location

- **Problem:** Creates inconsistency, violates project conventions
- **Fix:** Always resolve workspace root from `ArtifactRegistry["worktrees"]`.

### Proceeding with failing tests

- **Problem:** Can't distinguish new bugs from pre-existing issues
- **Fix:** Report failures, get explicit permission to proceed

## Red Flags

**Never:**
- Create a worktree when Step 0 detects existing isolation
- Use `git worktree add` when you have a native worktree capability. This is the #1 mistake — if you have it, use it.
- Skip Step 1a by jumping straight to Step 1b's git commands
- Create worktree without verifying it's ignored
- Skip baseline test verification
- Proceed with failing tests without asking
- Execute on current branch or disable isolation without `approval-manager` authorization and audit evidence
- Use wildcards or unresolved paths for workspace directories

**Always:**
- Run Step 0 detection first
- Prefer native capabilities over git fallback
- Resolve the workspace root from `ArtifactRegistry["worktrees"]`
- Verify directory is ignored
- Auto-detect and run project setup
- Verify clean test baseline
