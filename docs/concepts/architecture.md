# Architecture

gin-workflow is a plugin for Claude Code, Codex, Antigravity, and OpenCode that moves a change from requirement to merge through recorded gates. GitHub Copilot CLI also loads its skills and hooks, but it cannot be the configured harness, so workers and reviews run on one of the others. Skills tell the agent what to do at each stage. The `gin-workflow` Python CLI records the gates and derives the workflow state from them. A task tracker (local Markdown files, or Beads if you choose it) tracks the work. This page shows how the pieces fit. Each diagram links to the page that covers it in detail.

## Components

```mermaid
flowchart LR
    subgraph Harnesses
        CC[Claude Code]
        CX[Codex]
        AG[Antigravity agy]
        OC[OpenCode]
    end
    subgraph Bundle["Plugin bundle (dist/&lt;harness&gt;)"]
        SK[skills/ stage and support skills]
        AGT[agents/ developer, code-reviewer, ...]
        REF[references/ stage-contract, shape-*]
        RUL[rules/ rule packs]
        HK[hooks/hooks.json: scripts/safety-check.sh, post-edit.sh]
        CLI[gin-workflow CLI: workflow_core]
        RL[review-ledger.py: review_ledger]
    end
    subgraph EXT["gin-orchestrator extension (optional)"]
        ORC[gin-orchestrator CLI: gin_orchestrator routed workers]
    end
    subgraph Repo["Your repository"]
        CFG[.agent-workflow/ config, generated, runtime/events.jsonl]
        PLN[.planning/ specs, plans, reviews, worktrees]
        TK[(Tasks: .planning/tasks or Beads)]
        GIT[(git branches and worktrees)]
    end
    CC & CX & AG & OC --> SK
    SK --> AGT
    SK --> REF
    SK --> CLI
    SK --> RL
    CLI --> RUL
    CLI --> CFG
    CLI --> TK
    RL --> PLN
    RL --> GIT
    CLI -->|delegates when installed| ORC
    ORC -->|imports only workflow_core.ext| CLI
    ORC --> CC & CX & AG & OC
    HK -.guards.-> GIT
```

The harness loads the skills. Skills call `gin-workflow` for configuration, gates, rules, specs, team mode, and usage, and `review-ledger.py` for reviews. Tasks go through `gin-workflow task`, which serves Markdown files or runs `bd`. `gin-orchestrator` is an optional extension: `gin-workflow` calls it through a versioned CLI contract ([Orchestrator contract](../reference/orchestrator-contract.md)), and it reaches back only through the facade `workflow_core.ext`; `gin-workflow` never imports it. Nothing outside the repository holds workflow state except Beads (if used) and the harness logs that `usage collect` reads. See [State model](state-model.md) for who owns what.

## Lifecycle

```mermaid
stateDiagram-v2
    [*] --> discuss
    discuss --> plan: requirement_confirmed
    plan --> orchestrate: plan_approved
    orchestrate --> execute: orchestration_ready
    execute --> execute: next ready track
    execute --> ship: implementation_complete
    ship --> [*]: shipped
    [*] --> quick: small change
    quick --> [*]: quick_completed
    execute --> progress: blocked or held
    progress --> execute: blocker cleared or gate waived
    note right of execute
        each track: implement, independent review,
        usage collect, task close
    end note
    note left of plan
        SDD layout: change folder and REQ-IDs
        team mode: gates proven by pull requests
    end note
```

Each arrow is a gate recorded with `gin-workflow record` or derived from the task tracker. `gin-workflow state` evaluates the gates and names exactly one next stage, or holds at `progress` with remedies. See [Lifecycle](lifecycle.md).

## One track, from claim to close

```mermaid
sequenceDiagram
    autonumber
    participant A as Main agent (execute)
    participant D as Developer subagent
    participant B as Task tracker (gin-workflow task)
    participant W as Worktree
    participant R as gin-workflow rules
    participant L as review-ledger.py
    participant V as Independent reviewer
    participant U as gin-workflow usage
    A->>B: task ready, task update --status in_progress
    A->>R: rules --files <scope>
    R-->>A: rule text for the developer
    A->>D: spawn at the model and effort from routes dispatch
    D->>W: failing test, code, tests pass, commit in .planning/worktrees/<id>
    D-->>A: done, needs_clarification, failed, or blocked
    A->>L: init, checkpoint, transition-requested
    V->>L: start-review, add-finding or approve
    alt changes requested
        D->>W: fix at the same route
        A->>L: fix-finding, new checkpoint
        V->>L: verify-finding, approve
    end
    A->>U: usage collect --bead <id> --best-effort
    A->>B: task close <id>
    B-->>A: dependents become ready
```

A track closes when its tests pass and its review is approved, without waiting for a merge; that unblocks the next track. The reviewer runs in a fresh session of the main harness, or on a different provider with gin-orchestrator, within `routing.review.max_cycles`. See [Lifecycle](lifecycle.md#execute-and-review).

## Provider routing

```mermaid
flowchart TD
    T[Plan track: provider role + catalog model and effort] --> F[gin-workflow routes resolve]
    F --> Q{provider_mode multi and gin-orchestrator available?}
    Q -->|no, or it failed: warning| MH[every route is the main harness]
    Q -->|yes| OR[gin-orchestrator routes resolve]
    C1[orchestrator.roles: preferred, fallback, by_tier] --> OR
    C2[orchestrator.local.yaml: executable per harness] --> OR
    C3[config.yaml models: catalog per harness] --> OR
    OR -->|diagnostics| X[exit 2: report every diagnostic, write no manifest]
    MH -->|diagnostics| X
    OR --> M[gin-workflow writes runtime/assignments/&lt;workflow&gt;.yaml]
    MH --> M
    M -->|with gin-orchestrator| D[gin-orchestrator dispatches a worker]
    D --> H{health, circuit breaker, capacity}
    H -->|unavailable| N[next candidate, route mapped by rank]
    N --> H
    H -->|allowed| RUN[run native CLI: claude, codex, agy, opencode]
    N -->|none left before queue deadline| U[worker_routes_unavailable: task stays open]
```

Plans name roles and routes from the main harness's model catalog, never providers. `gin-workflow` resolves the routes and writes the manifest. It delegates the resolution, and the reviewer choice, to `gin-orchestrator` only when `provider_mode` is `multi` and that extension is installed. Without it every route is the main harness. Executables come from machine-local configuration and are rechecked at dispatch. Every candidate runs the plan's route mapped by rank into its own catalog, so a fallback keeps the rank. See [Providers](providers.md) and [Orchestrator](../orchestrator/README.md).

## Build and install

```mermaid
flowchart LR
    S[plugins/&lt;plugin&gt;/src: gin-workflow, gin-qa, gin-orchestrator] --> I[install.sh / install.ps1]
    I --> D1[dist/claude-code]
    I --> D2[dist/codex]
    I --> D3[dist/antigravity]
    I --> D4[dist/opencode]
    I --> D5[dist/copilot/&lt;plugin&gt;]
    I --> LCH[~/.local/bin launchers: gin-workflow, gin-qa, gin-orchestrator]
    D1 --> C1[~/.claude/skills/&lt;plugin&gt;]
    D2 --> C2[codex plugin add: cached snapshot]
    D3 --> C3[agy plugin install]
    D4 --> C4[~/.config/opencode/skills/&lt;plugin&gt;]
    D5 --> C5[copilot plugin install]
    MK[marketplace: claude plugin install, codex plugin add] --> C1b[harness plugin cache]
```

The installer rebuilds `dist/` from `src/` for each selected platform and registers it with the harness. Three plugins build the same way: `gin-workflow` (the default), `gin-qa`, and `gin-orchestrator`. `--plugin gin-orchestrator` installs gin-workflow first when the gin-workflow launcher is missing or at another version. Each harness keeps a snapshot, so a fix committed to this repository reaches a machine only after the install runs again there. A marketplace install copies the plugin but not the launchers. See [Contributing](../contributing.md) and [Troubleshooting](../reference/troubleshooting.md).

## Usage collection

```mermaid
flowchart LR
    L1[~/.claude/projects/&lt;repo&gt;/*.jsonl] --> A
    L2[~/.codex/sessions/**/rollout-*.jsonl] --> A
    A[usage_logs: token records per model] --> B{usage_attribution}
    B -->|inside a worktree| T[track bead: execute or review]
    B -->|repository root| G[next gate: discuss, plan, orchestrate, quick, ship]
    B -->|neither| UA[epic: unattributed]
    T & G & UA --> S[usage: cost from usage-prices.yaml + quality signals]
    S --> M[(bead metadata ai_usage)]
    M --> R[gin-workflow usage report and /report]
```

`execute` and `ship` run `usage collect --best-effort` before closing a bead, so a collection error never blocks the close. It keeps only the timestamp, model, session, working directory, branch, and token counts of each log entry, never prompt text. See [Usage report](../guides/usage-report.md).
