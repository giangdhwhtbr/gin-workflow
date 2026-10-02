# Benchmark Protocol

Compares the token cost and outcome of gin-workflow against other agent workflows on the same tasks. Runs are manual and are not part of CI.

## Sample

- One pinned React + TypeScript + Vite repository. Record its URL and commit SHA in every result file; every run starts from a clean checkout of that commit.

## Tasks

1. **Small bug fix:** one defect with a failing test or a reproducible symptom.
2. **Medium feature:** one component plus its state handling plus tests.

Write each task prompt once and reuse it verbatim for every configuration.

## Configurations

| Label | Setup |
|---|---|
| `gin-easy` | gin-workflow, rigor `easy`, task run through `/quick` |
| `gin-standard` | gin-workflow, rigor `standard`, full lifecycle |
| `superpowers` | superpowers plugin, its default flow |
| `spec-kit` | spec-kit, its default flow |

Use the same harness (Claude Code) and the same model for every configuration. Record the version of each framework.

## Metrics

- Input, output, cache-write and cache-read tokens.
- Tool calls.
- Wall time in seconds.
- Whether the task's tests pass.

A run whose tests fail is reported as **failed**, not as cheaper.

## Collecting

Claude Code stores each session transcript at `~/.claude/projects/<project>/<session>.jsonl`. Summarize one or more runs:

```bash
python3 scripts/benchmark/summarize_usage.py gin-easy=<path> superpowers=<path>
```

The command prints one Markdown table row per label.

## Recording results

Write each benchmark to `docs/benchmarks/YYYY-MM-DD-<sample>.md` with the sample commit, the task prompts, the framework versions, the summary table, and the test outcome of each run.
