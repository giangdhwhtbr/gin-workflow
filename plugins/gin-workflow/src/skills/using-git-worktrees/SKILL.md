---
name: using-git-worktrees
description: Use this skill before executing an implementation plan to ensure work happens in an isolated workspace. First detects whether you're already in a worktree; if not, prefers the platform's native worktree tools; falls back to git worktree creation only when no native tool is available.
---

# Using git worktrees

Implementation work belongs in an isolated workspace so the main checkout stays clean and so accidental commits, broken builds, or experimental changes don't pollute the user's primary branch.

This skill is about routing — picking the right mechanism for *this* environment in *this* state — not about preferring git worktrees over everything else. Detection comes first; native tools come second; manual `git worktree add` is the fallback when nothing else applies.

**Announce at start:** "Setting up an isolated workspace via `:using-git-worktrees`."

## Step 0 — Detect existing isolation

Before creating anything, check whether the current directory is already an isolated workspace.

```bash
GIT_DIR=$(cd "$(git rev-parse --git-dir)" 2>/dev/null && pwd -P)
GIT_COMMON=$(cd "$(git rev-parse --git-common-dir)" 2>/dev/null && pwd -P)
BRANCH=$(git branch --show-current)
```

When `GIT_DIR != GIT_COMMON`, the directory is either a linked worktree *or* inside a git submodule. Distinguish them:

```bash
# If this returns a path, you're in a submodule, not a worktree
git rev-parse --show-superproject-working-tree 2>/dev/null
```

**If `GIT_DIR != GIT_COMMON` and not inside a submodule:** you are already in a linked worktree. Skip to Step 3 (project setup). Do NOT create another worktree on top.

Report concisely:

- On a branch: "Already in an isolated workspace at `<path>` on branch `<name>`."
- Detached HEAD: "Already in an isolated workspace at `<path>` (detached HEAD; branch creation will be needed before ship)."

**If `GIT_DIR == GIT_COMMON` (or you're inside a submodule):** the current directory is a normal repository checkout. Continue to Step 1.

## Step 1 — Create the isolated workspace

You have two mechanisms. Try them in order.

### 1a. Native worktree tools (preferred)

If your platform provides a worktree-creation tool — names vary, but look for things like `EnterWorktree`, `WorktreeCreate`, a `/worktree` slash command, or a `--worktree` flag on the surrounding harness — use it. Native tools manage their own directory layout, branch creation, and cleanup; the harness expects to see worktrees it created itself.

Using `git worktree add` when the platform already has a native tool creates phantom state the harness can't see, schedule, or clean up. Don't fight the harness.

If a native tool exists, use it and skip to Step 3. Only proceed to Step 1b if no native tool is available.

### 1b. Git worktree fallback

Only reach this branch when no native tool is available. Manually create a worktree using git.

But first, ask for consent unless the user has already declared a worktree preference in their session instructions:

> "Want me to set up an isolated worktree? It protects your current branch from changes and keeps the main checkout clean."

If the user declines, work in place and skip to Step 3.

#### Pick the worktree directory

Follow this priority. An explicit user preference always beats observed filesystem state.

1. **Declared preference** — if the user has specified a worktree directory in their instructions, use it without asking.
2. **Existing project-local directory:**

   ```bash
   ls -d .worktrees 2>/dev/null     # preferred (hidden)
   ls -d worktrees  2>/dev/null     # also acceptable
   ```

   If both exist, use `.worktrees`.

3. **Existing global directory:**

   ```bash
   project=$(basename "$(git rev-parse --show-toplevel)")
   ls -d ~/.config/claude-draft/worktrees/$project 2>/dev/null
   ```

   If found, use it.

4. **Default** — if nothing applies, create `.worktrees/` at the project root.

#### Verify ignore status (project-local directories only)

Before creating a worktree inside the project tree, confirm the directory is gitignored:

```bash
git check-ignore -q .worktrees 2>/dev/null \
  || git check-ignore -q worktrees 2>/dev/null
```

If neither exits cleanly, the directory isn't ignored and a worktree there would pollute `git status`. Add it to `.gitignore`, commit the change, and only then create the worktree.

Global directories (`~/.config/claude-draft/worktrees/...`) live outside the project and need no check.

#### Create the worktree

```bash
project=$(basename "$(git rev-parse --show-toplevel)")

# project-local: path="$LOCATION/$BRANCH_NAME"
# global:        path="~/.config/claude-draft/worktrees/$project/$BRANCH_NAME"

git worktree add "$path" -b "$BRANCH_NAME"
cd "$path"
```

**Sandbox fallback:** if `git worktree add` fails with a permission error (typical inside locked-down sandboxes), tell the user that the sandbox blocked worktree creation and you'll work in the current directory instead. Then run setup and the baseline check in place.

## Step 3 — Project setup

Auto-detect the project type and run the appropriate setup:

```bash
# Node.js
if [ -f package.json ]; then npm install; fi

# Rust
if [ -f Cargo.toml ]; then cargo build; fi

# Python
if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
if [ -f pyproject.toml ]; then poetry install || pip install -e .; fi

# Go
if [ -f go.mod ]; then go mod download; fi
```

Skip silently when the project doesn't match any of these — the user may use a different toolchain that doesn't need installation.

## Step 4 — Baseline check

Confirm tests pass before any work begins. Without this baseline you can't tell whether failures later are new or pre-existing.

```bash
# project-appropriate test command, e.g.
npm test
cargo test
pytest
go test ./...
```

**If tests fail:** report the failures and ask the user whether to proceed or investigate first. Don't silently start implementing on top of a red baseline — every later failure becomes ambiguous.

**If tests pass:** report ready.

### Report format

```
Worktree ready at <full-path>
Tests passing (<N> tests, 0 failures)
Ready to implement <feature-name>
```

## Quick reference

| Situation | Action |
|-----------|--------|
| Already in a linked worktree | Skip creation (Step 0) |
| In a submodule | Treat as normal repo (Step 0 guard) |
| Native worktree tool available | Use it (Step 1a), skip git fallback |
| No native tool | Git worktree fallback (Step 1b) |
| `.worktrees/` exists | Use it after verifying ignored |
| `worktrees/` exists | Use it after verifying ignored |
| Both exist | Use `.worktrees/` |
| Neither exists | Check user preference, then default to `.worktrees/` |
| Global path exists | Use it (backward compat) |
| Directory not gitignored | Add to `.gitignore` and commit before creating |
| Permission error on create | Sandbox fallback; work in place |
| Baseline tests fail | Report and ask; don't implement on red |
| No `package.json` / `Cargo.toml` | Skip dependency install silently |

## Common mistakes

### Fighting the harness

If the platform has a native worktree tool and you reach for `git worktree add` instead, you create state the harness can't see — it can't list it, clean it up, or route subsequent operations correctly. Step 1a exists specifically to prevent this.

### Skipping the detection step

If you create a worktree without first checking whether you're already in one, you end up with nested worktrees: confusing to navigate, harder to clean up, and a source of "where did I commit that?" stories. Always run Step 0 first.

### Skipping the gitignore check

A project-local worktree directory that isn't gitignored will pollute `git status` and risk being committed accidentally. The check is one command; run it.

### Assuming the directory location

The priority order (declared preference → existing project-local → existing global → default) keeps the workspace consistent across runs. Skipping the priority and creating "wherever feels right" produces drift between sessions and makes the setup harder to reason about.

### Proceeding with a failing baseline

If tests fail before you've changed anything, every later failure is ambiguous: did you introduce it, or was it already broken? Confirm green before starting, or get explicit permission to start on red.

## Things to avoid

- Creating a worktree when Step 0 already detected isolation.
- Calling `git worktree add` when a native worktree tool is available.
- Skipping Step 1a and going straight to manual git commands.
- Creating a project-local worktree directory without verifying it's gitignored.
- Skipping the baseline test verification.
- Continuing past failing baseline tests without explicit consent.

## Where this skill sits

| Aspect | Detail |
|--------|--------|
| Direct skill call | `:using-git-worktrees` |
| Called by | `:writing-plans` handoff (before `/execute`), `:executing-plans`, `:subagent-driven-development` |
| Default global path | `~/.config/claude-draft/worktrees/<project>/<branch>` |
| Default project-local path | `.worktrees/<branch>` (must be gitignored) |
| Hands off to | the calling skill, with the worktree as the new working directory |
