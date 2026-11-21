# Architecture

gin-workflow is a plugin for Claude Code, Codex, Antigravity, OpenCode, and GitHub Copilot CLI that moves a change from requirement to merge through recorded gates. Skills tell the agent what to do at each stage. The `gin` Python CLI records the gates and derives the workflow state from them. A task tracker (local Markdown files, or Beads if you choose it) tracks the work. This page shows how the pieces fit. Each diagram links to the page that covers it in detail.

## Components

```mermaid
flowchart LR
    subgraph Harnesses
        CC[Claude Code]
        CX[Codex]
        AG[Antigravity agy]
        OC[OpenCode]
        CP[Copilot CLI]
    end
    subgraph Bundle["Plugin bundle (dist/&lt;harness&gt;)"]
        SK[skills/ stage and support skills]
        AGT[agents/ developer, code-reviewer, ...]
        REF[references/ stage-contract, shape-*]
        RUL[rules/ rule packs]
        HK[hooks/hooks.json: scripts/safety_check.py]
        CLI[gin CLI: workflow_core]
        RL[review-ledger.py: review_ledger]
    end
    subgraph ADD["gin-ba add-on (optional)"]
        BA[skills/ capture, mockup]
    end
    subgraph Repo["Your repository"]
        CFG[.agent-workflow/ config, generated, runtime/events.jsonl]
        PLN[.planning/ specs, plans, reviews, worktrees]
        TK[(Tasks: .planning/tasks or Beads)]
        GIT[(git branches and worktrees)]
        AST[docs/specs/&lt;capability&gt;/assets/&lt;date&gt;: BA inputs, SDD layout]
    end
    CC & CX & AG & OC & CP --> SK
    CC & CX & AG & OC & CP --> BA
    BA -->|gin specs assets| AST
    SK -->|discuss cites confirmed folders| AST
    SK --> AGT
    SK --> REF
    SK --> CLI
    SK --> RL
    CLI --> RUL
    CLI --> CFG
    CLI --> TK
    RL --> PLN
    RL --> GIT
    HK -.guards.-> GIT
```

The harness loads the skills. Skills call `gin` for configuration, gates, rules, specs, and team mode; they call `review-ledger.py` for reviews. Tasks go through `gin task`, which serves Markdown files or runs `bd`. Nothing outside the repository holds workflow state except Beads (if used). See [State model](state-model.md) for who owns what.

The optional `gin-ba` add-on has skills only and no CLI. With the SDD layout, `capture` and `mockup` write the business analyst's inputs into dated asset folders under `docs/specs/<capability>/assets/` through `gin specs assets`. `discuss` cites the confirmed folders. See [Business analyst](../guides/ba.md).

## Lifecycle

```mermaid
stateDiagram-v2
    state "BA inputs: gin-ba capture, mockup" as ba_inputs
    [*] --> ba_inputs: SDD layout, optional
    ba_inputs --> discuss: Confirmed date
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
        task close
    end note
    note left of plan
        SDD layout: change folder and REQ-IDs
        team mode: gates proven by pull requests
    end note
    note right of discuss
        after the spec: gin specs export (SRS),
        /gin:explain (interactive page)
    end note
```

Each arrow between stages is a gate recorded with `gin record` or derived from the task tracker. `gin state` evaluates the gates and names exactly one next stage, or holds at `progress` with remedies. The `ba_inputs` state and the SRS export and explain page after the spec record no gate; the BA confirms inputs with `Confirmed: <date>` in the folder's `description.md`. See [Lifecycle](lifecycle.md) and [Business analyst](../guides/ba.md).

## One track, from claim to close

```mermaid
sequenceDiagram
    autonumber
    participant A as Main agent (execute)
    participant D as Developer subagent
    participant B as Task tracker (gin task)
    participant W as Worktree
    participant R as gin rules
    participant L as review-ledger.py
    participant V as Independent reviewer
    A->>B: task ready, task update --claim
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
    A->>B: task close <id>
    B-->>A: dependents become ready
```

A track closes when its tests pass and its review is approved, without waiting for a merge; that unblocks the next track. The reviewer runs in a fresh session of the main harness within `routing.review.max_cycles`. See [Lifecycle](lifecycle.md#execute-and-review).

## Provider routing

```mermaid
flowchart TD
    T[Plan track: provider role + catalog model and effort] --> F[gin routes resolve]
    C3[config.yaml models: catalog per harness] --> F
    F -->|diagnostics| X[exit 2: report every diagnostic, write no manifest]
    F --> MH[every route is the main harness]
    MH --> M[gin-workflow writes runtime/assignments/&lt;workflow&gt;.yaml]
```

Plans name roles and routes from the main harness's model catalog, never providers. gin-workflow resolves every route to the main harness and writes the manifest. See [Providers](providers.md).

## Build and install

```mermaid
flowchart LR
    S[plugins/&lt;plugin&gt;/src: gin-workflow, gin-qa, gin-ba] --> I[install.sh / install.ps1]
    I --> D1[dist/claude-code]
    I --> D2[dist/codex]
    I --> D3[dist/antigravity]
    I --> D4[dist/opencode]
    I --> D5[dist/copilot/&lt;plugin&gt;]
    I --> LCH[~/.local/bin launchers: gin, gin-qa]
    D1 --> C1[~/.claude/skills/&lt;plugin&gt;]
    D2 --> C2[codex plugin add: cached snapshot]
    D3 --> C3[agy plugin install]
    D4 --> C4[~/.config/opencode/skills/&lt;plugin&gt;]
    D5 --> C5[copilot plugin install]
    MK[marketplace: claude plugin install, codex plugin add] --> C1b[harness plugin cache]
```

The installer rebuilds `dist/` from `src/` for each selected platform and registers it with the harness. Three plugins build the same way: gin-workflow (the default, plugin id `gin`), `gin-qa`, and `gin-ba`. Each harness keeps a snapshot, so a fix committed to this repository reaches a machine only after the install runs again there. A marketplace install copies the plugin but not the launchers. See [Contributing](../contributing.md) and [Troubleshooting](../reference/troubleshooting.md).
