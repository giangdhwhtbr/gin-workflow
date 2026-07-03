# Worker Prompt Templates

Two templates the orchestrator uses to build subagent prompts in Phase 3. Choose based
on `dispatch_mode` determined in Phase 1 (OV1 verification).

**Path B note:** Path B exists for harnesses where the Skill tool is not available in
subagents. OV1 from Task 1 verifications determines which path to use. As of 2026-05-07
this machine confirmed Path A works (`dispatch_mode=skill`).

---

## Template (Path A — skill available)

Use when `dispatch_mode = "skill"`. The orchestrator fills all `{{placeholders}}` before
passing this as the Task() prompt body.

````markdown
## Worker inputs

```yaml
epic_id:           "{{epic_id}}"
agent_name:        "{{agent_name}}"
coordinator_name:  "{{coordinator_name}}"
track_thread_id:   "{{track_thread_id}}"   # format: track-<agent_name>-<epic_id> (dashes, NOT colons)
bead_ids:          {{bead_ids_json}}        # JSON array, e.g. ["bd-001","bd-002"]
bead_titles:       {{bead_titles_json}}     # JSON object mapping bead_id → title, e.g. {"bd-001":"Add SDK","bd-002":"Write tests"}
file_scope:        {{file_scope_json}}      # JSON array of globs
file_scope_regex:  "{{file_scope_regex}}"  # pre-computed regex from file_scope globs, e.g. "^(packages/sdk|apps/api)/"
project_key:       "{{project_key}}"        # absolute path of original repo root
mode:              "{{mode}}"               # "shared" | "worktree"
integration_branch: "{{integration_branch}}"
{{#if mode == "worktree"}}
worktree_path:     "{{worktree_path}}"
worktree_branch:   "{{worktree_branch}}"
{{/if}}
{{#if mode == "shared"}}
test_cmd_template: "{{test_cmd_template}}"  # use {path} placeholder
{{/if}}
```

### Step 0 — Export inputs as shell variables

Before running any shell snippet from the worker protocol, export the following from
the YAML inputs above:

```bash
export EPIC_ID="<epic_id>"
export AGENT_NAME="<agent_name>"
export COORDINATOR_NAME="<coordinator_name>"
export TRACK_THREAD_ID="<track_thread_id>"
export INTEGRATION_BRANCH="<integration_branch>"
export PROJECT_KEY="<project_key>"
export FILE_SCOPE_REGEX="<file_scope_regex>"
# mode=worktree only:
export WORKTREE_PATH="<worktree_path>"
# mode=shared only:
export TEST_CMD_TEMPLATE="<test_cmd_template>"
# Per-bead, set inside the Step 1–3 loop:
# export BEAD_ID=<current bead id>
# export TITLE=<title for current bead from bead_titles map>
```

Note: `bead_ids` is a list — the protocol's "Loop steps 1–3 for each bead_id" iterates
this list, exporting `$BEAD_ID` and `$TITLE` per iteration (look up title from
`bead_titles`). `$FILE_SCOPE_REGEX` is computed by the orchestrator from `file_scope`
globs (e.g. `["packages/sdk/**", "apps/api/**"]` → `^(packages/sdk|apps/api)/`) and
provided as the `file_scope_regex` input.

## Instructions

**Action:** Invoke the `bead-worker` skill via the Skill tool. The inputs above are in
the prompt body; no `args` parameter needed.

Follow the bead-worker protocol for each bead_id in order.

Your FINAL assistant message MUST be the JSON return contract defined in
`~/.claude/skills/bead-orchestrator/references/return-schema.md`.
Output ONLY the JSON object — no prose before or after it.
````

---

## Template (Path B — skill unavailable, inline)

Use when `dispatch_mode = "inline"`. The orchestrator reads
`~/.claude/skills/bead-worker/SKILL.md` at runtime, strips the YAML frontmatter
(everything up to and including the closing `---`), and substitutes the body verbatim
in place of `{{BEAD_WORKER_SKILL_BODY}}`.

````markdown
## Worker inputs

```yaml
epic_id:           "{{epic_id}}"
agent_name:        "{{agent_name}}"
coordinator_name:  "{{coordinator_name}}"
track_thread_id:   "{{track_thread_id}}"   # format: track-<agent_name>-<epic_id> (dashes, NOT colons)
bead_ids:          {{bead_ids_json}}
bead_titles:       {{bead_titles_json}}     # JSON object mapping bead_id → title
file_scope:        {{file_scope_json}}
file_scope_regex:  "{{file_scope_regex}}"  # pre-computed regex from file_scope globs
project_key:       "{{project_key}}"
mode:              "{{mode}}"
integration_branch: "{{integration_branch}}"
{{#if mode == "worktree"}}
worktree_path:     "{{worktree_path}}"
worktree_branch:   "{{worktree_branch}}"
{{/if}}
{{#if mode == "shared"}}
test_cmd_template: "{{test_cmd_template}}"
{{/if}}
```

### Step 0 — Export inputs as shell variables

Before running any shell snippet from the worker protocol, export the following from
the YAML inputs above:

```bash
export EPIC_ID="<epic_id>"
export AGENT_NAME="<agent_name>"
export COORDINATOR_NAME="<coordinator_name>"
export TRACK_THREAD_ID="<track_thread_id>"
export INTEGRATION_BRANCH="<integration_branch>"
export PROJECT_KEY="<project_key>"
export FILE_SCOPE_REGEX="<file_scope_regex>"
# mode=worktree only:
export WORKTREE_PATH="<worktree_path>"
# mode=shared only:
export TEST_CMD_TEMPLATE="<test_cmd_template>"
# Per-bead, set inside the Step 1–3 loop:
# export BEAD_ID=<current bead id>
# export TITLE=<title for current bead from bead_titles map>
```

Note: `bead_ids` is a list — the protocol's "Loop steps 1–3 for each bead_id" iterates
this list, exporting `$BEAD_ID` and `$TITLE` per iteration (look up title from
`bead_titles`). `$FILE_SCOPE_REGEX` is computed by the orchestrator from `file_scope`
globs (e.g. `["packages/sdk/**", "apps/api/**"]` → `^(packages/sdk|apps/api)/`) and
provided as the `file_scope_regex` input.

## Instructions

You are a bead-worker subagent. The skill body below defines your full protocol.
Follow it exactly for each bead_id in order.

---

{{BEAD_WORKER_SKILL_BODY}}

---

Your FINAL assistant message MUST be the JSON return contract defined in
`~/.claude/skills/bead-orchestrator/references/return-schema.md`.
Output ONLY the JSON object — no prose before or after it.
````

### How the orchestrator reads SKILL.md for Path B

```python
import re

skill_path = Path.home() / ".claude/skills/bead-worker/SKILL.md"
raw = skill_path.read_text()

# Strip YAML frontmatter (everything between the first two "---" lines)
body = re.sub(r'^---\n.*?\n---\n', '', raw, count=1, flags=re.DOTALL).strip()

prompt = template_path_b.replace("{{BEAD_WORKER_SKILL_BODY}}", body)
```
