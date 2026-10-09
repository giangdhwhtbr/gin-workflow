# Recommended Tools

gin-workflow runs with only the [required dependencies](../../README.md#1-dependencies). The tools below are optional; each one improves a specific part of the workflow, and everything falls back cleanly without them.

## CodeGraph

[CodeGraph](https://github.com/colbymchenry/codegraph) indexes a repository into a local graph of symbols, call edges, and files. One `codegraph explore "<symbols or question>"` returns the relevant source plus the call paths between them, replacing a loop of grep and file reads. gin-workflow agents use it when the repository has a `.codegraph/` index and fall back to grep and read otherwise.

### Install

```bash
# macOS / Linux
curl -fsSL https://raw.githubusercontent.com/colbymchenry/codegraph/main/install.sh | sh
# Windows (PowerShell)
irm https://raw.githubusercontent.com/colbymchenry/codegraph/main/install.ps1 | iex
# or, with Node
npm i -g @colbymchenry/codegraph
```

Check with `codegraph --version`.

### Configure

- **Index each repository** once with `codegraph init` in its root. On a brownfield or legacy repository, `/gin-workflow:setup` offers to run it for you. The index lives in `.codegraph/`; add `.codegraph/` to the repository's `.gitignore`, because git otherwise lists the folder as untracked.
- **Optional MCP server:** `codegraph install` adds CodeGraph's MCP tools to Claude Code, Codex, and other supported agents (one global run covers every project). gin-workflow's skills call the `codegraph` CLI, so the MCP server is not required; it adds a file watcher that keeps the index current while you edit.

### Where gin-workflow uses it

| Where | How |
|---|---|
| Every lifecycle stage ([stage contract](../../plugins/gin-workflow/src/references/stage-contract.md)) | looks up symbols, tests, and knowledge with `codegraph explore` before grep |
| `agent-researcher`, `developer`, `docs-writer` agents | look up related code with `codegraph explore` |
| `code-reviewer` agent | looks up callers; runs `codegraph impact` / `codegraph callers` on changed public symbols |
| `/gin-workflow:tech-doc` | `codegraph files` for structure, `codegraph explore` for subsystems |
| `/gin-workflow:setup` | offers `codegraph init`, or suggests installing CodeGraph |
| `gin-workflow setup doctor` | reports whether CodeGraph is installed and whether the index is older than `HEAD` (then run `codegraph sync`) |

### Known limitation: worktrees

A git worktree has no `.codegraph/` of its own, so agents working in one fall back to grep and read. The main checkout's index is not used there because it reflects another branch. To use CodeGraph in a worktree, run `codegraph init` inside it, and `codegraph uninit -f` before removing the worktree: an untracked `.codegraph/` makes `git worktree remove` fail.

## Other optional tools

| Tool | For | Set up |
|---|---|---|
| Codex CLI (`codex`), Antigravity CLI (`agy`), or OpenCode (`opencode`) next to your main harness | [multi-provider routing](../concepts/providers.md) | install the CLI, then choose models with `gin-workflow setup models` |
| GitHub CLI (`gh`) or GitLab CLI (`glab`) | [team mode](team.md) | your package manager, then `gh auth login` or `glab auth login` |
| Node with `@playwright/test` 1.49 or later | [QA end-to-end specs](qa.md) | `npm i -D @playwright/test` and `npx playwright install` in the application repository |
