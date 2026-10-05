# Architecture

gin-workflow is a plugin for Claude Code, Codex, and Antigravity that walks a change from requirement to merge through recorded gates. Skills tell the agent what to do at each stage; a small Python CLI keeps durable state honest; Beads tracks the work. This page shows how the pieces fit. Each diagram links to the page that covers it in detail.

## Components

```mermaid
flowchart LR
    subgraph Harnesses
        CC[Claude Code]
        CX[Codex]
        AG[Antigravity agy]
    end
    subgraph Bundle["Plugin bundle (dist/&lt;harness&gt;)"]
        SK[skills/ stage and support skills]
        AGT[agents/ developer, code-reviewer, ...]
        REF[references/ stage-contract, shape-*]
        RUL[rules/ rule packs]
        HK[hooks/hooks.json: scripts/safety-check.sh, post-edit.sh]
        CLI[gin-workflow CLI: workflow_core]
        RL[review-ledger.py: review_ledger]
        PRV[workflow_providers: routed workers]
    end
    subgraph Repo["Your repository"]
        CFG[.agent-workflow/ config, generated, runtime/events.jsonl]
        PLN[.planning/ specs, plans, reviews, worktrees]
        BD[(Beads: bd)]
        GIT[(git branches and worktrees)]
    end
    CC & CX & AG --> SK
    SK --> AGT
    SK --> REF
    SK --> CLI
    SK --> RL
    SK --> BD
    CLI --> RUL
    CLI --> CFG
    CLI --> BD
    RL --> PLN
    RL --> GIT
    PRV --> CC & CX & AG
    HK -.guards.-> GIT
```

The harness loads skills; skills call `gin-workflow` for configuration, gates, rules, specs, team mode, and usage, `review-ledger.py` for reviews, and `bd` for tasks. Nothing outside the repository holds workflow state except Beads and the harness logs that `usage collect` reads. See [State model](state-model.md) for who owns what.

## Lifecycle

```mermaid
stateDiagram-v2
    [*] --> discuss
    discuss --> plan: requirement_confirmed
    plan --> orchestrate: plan_approved
    orchestrate --> execute: orchestration_ready
    execute --> execute: next ready track
    execute --> verify: implementation_complete
    verify --> ship: verification_passed
    ship --> [*]: shipped
    [*] --> quick: small change
    quick --> [*]: quick_completed
    execute --> progress: blocked or held
    progress --> execute: blocker cleared or gate waived
    note right of execute
        each track: implement, independent review,
        usage collect, bd close
    end note
    note left of plan
        SDD layout: change folder and REQ-IDs
        team mode: gates proven by pull requests
    end note
```

Each arrow is a gate recorded with `gin-workflow record` or derived from Beads. `gin-workflow state` evaluates the gates and names exactly one next stage, or holds at `progress` with remedies. A process gate can be waived with a reason; a safety gate needs a follow-up bead. See [Lifecycle](lifecycle.md).

## One track, from claim to close

```mermaid
sequenceDiagram
    autonumber
    participant A as Main agent (execute)
    participant B as Beads (bd)
    participant W as Worktree
    participant R as gin-workflow rules
    participant L as review-ledger.py
    participant V as Independent reviewer
    participant U as gin-workflow usage
    A->>B: bd ready, bd update --status in_progress
    A->>W: work in .planning/worktrees/<id>
    A->>R: rules --files <scope>
    R-->>A: rule text for the developer
    A->>W: failing test, code, tests pass, commit
    A->>L: init, checkpoint, transition-requested
    V->>L: start-review, add-finding or approve
    alt changes requested
        A->>L: fix-finding, new checkpoint
        V->>L: verify-finding, approve
    end
    A->>U: usage collect --bead <id> --best-effort
    A->>B: bd close <id>
    B-->>A: dependents become ready
```

A track closes when its tests pass and its review is approved, without waiting for a merge; that unblocks the next track. The reviewer runs on a different provider (or session) than the implementer, within `routing.review.max_cycles`. See [Lifecycle](lifecycle.md#execute-and-review).

## Provider routing

```mermaid
flowchart TD
    T[Plan track: provider role + reasoning low/medium/high] --> Q[AssignmentRequest]
    Q --> RA[resolve_all_assignments]
    C1[routing.roles: preferred, fallback, main_harness] --> RA
    C2[providers.local.yaml: executable + model per tier] --> RA
    RA -->|any track unresolved| X[stop: report every diagnostic]
    RA --> M[write_assignment_manifest: runtime/assignments/&lt;workflow&gt;.yaml]
    M --> D[RoutedWorkerDispatcher.dispatch]
    D --> H{health check}
    H -->|unhealthy| N[next candidate, same tier]
    H --> CB{circuit breaker and capacity}
    CB -->|open or full| N
    N --> H
    CB -->|allowed| RUN[run native CLI: claude, codex, agy]
    N -->|none left before queue deadline| U[worker_routes_unavailable: bead stays open]
```

Plans name roles and reasoning tiers only; concrete providers and models come from machine-local configuration at orchestration and are rechecked at dispatch. Fallback never lowers the reasoning tier. See [Providers](providers.md).

## Build and install

```mermaid
flowchart LR
    S[plugins/&lt;plugin&gt;/src] --> I[install.sh / install.ps1]
    I --> D1[dist/claude-code]
    I --> D2[dist/codex]
    I --> D3[dist/antigravity]
    I --> LCH[~/.local/bin/gin-workflow launcher]
    D1 --> C1[~/.claude/skills/&lt;plugin&gt;]
    D2 --> C2[codex plugin add: cached snapshot]
    D3 --> C3[agy plugin install]
    MK[marketplace: claude plugin install, codex plugin add] --> C1b[harness plugin cache]
```

The installer rebuilds `dist/` from `src/` for each selected platform and registers it with the harness. Each harness keeps a snapshot, so a fix committed to this repository reaches a machine only after the install runs again there. A marketplace install copies the plugin but not the `gin-workflow` launcher. See [Troubleshooting](../reference/troubleshooting.md).

## Usage collection

```mermaid
flowchart LR
    L1[~/.claude/projects/&lt;repo&gt;/*.jsonl] --> A
    L2[~/.codex/sessions/**/rollout-*.jsonl] --> A
    A[usage_logs: token records per model] --> B{usage_attribution}
    B -->|inside a worktree| T[track bead: execute or review]
    B -->|repository root| G[next gate: discuss, plan, orchestrate, verify, ship]
    B -->|neither| UA[epic: unattributed]
    T & G & UA --> S[usage: cost from usage-prices.yaml + quality signals]
    S --> M[(bead metadata ai_usage)]
    M --> R[gin-workflow usage report and /report]
```

`execute` and `ship` run `usage collect` before closing a bead; it reads only token counts and routing fields, never prompt text, and never blocks closing. See [Usage report](../guides/usage-report.md).
