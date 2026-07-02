---
name: test-driven-development
description: Red-green-refactor cycle for writing code from a failing test, through implementation, to a clean refactor that stays green.
---

# Test Driven Development Skill

This skill encodes the red-green-refactor cycle and the judgment of when to use it versus when another approach fits better. The final correctness gate is still verification-before-completion — TDD is the path there, not a replacement for it.

## The Red-Green-Refactor Cycle

1. **Red** — Write a failing test that captures one behavior the code must have. Run it and confirm it fails for the right reason (the production code does not yet implement the behavior), not for a trivial reason (a typo, a missing import, a wrong assertion). A test that fails for the wrong reason teaches nothing.
2. **Green** — Write the minimum production code that makes the test pass. Do not add behavior the test does not yet demand; speculative generality is added in the refactor step or, better, when a second test forces it.
3. **Refactor** — Improve the code's structure without changing behavior. Run the tests after each refactor step. If a test fails, you changed behavior — revert or fix, then continue. The tests are the safety net that makes refactoring safe.
4. **Repeat** — Move to the next behavior: another red test, then green, then refactor. Grow the implementation one behavior at a time.

The cycle is strict about order: a green test that was never red is not TDD — it is a test written after the fact. The value is in the red step, where the test's failure proves the production code is actually being exercised.

## When TDD Fits

Use TDD when:

- The behavior is well-specified enough to write an assertion before the implementation. Pure functions, parsers, state machines, and algorithms are the sweet spot.
- The cost of a bug is higher than the cost of the test (shared modules, data handling, money/security paths).
- You can run the tests fast enough that the red-green loop stays tight — seconds, not minutes.

## When TDD Does Not Fit

Skip strict TDD (write code first, then cover with tests before completion) when:

- The behavior is exploratory — you don't yet know what the output should be, so you can't assert it. Prototype first, then pin behavior with tests once the shape is known.
- The change is a one-shot configuration, a frontmatter edit, or documentation where the "test" is a human reading the result.
- The outer surface is UI or a long-running process where the meaningful check is manual verification (verification-before-completion's manual step), not an automated assertion.
- The test would only re-state the implementation in mock form, giving no independent signal.

In these cases, still add tests before declaring the work done — just write them after, and rely on verification-before-completion as the gate.

## Final Gate

TDD gets you to green incrementally, but "all my new tests pass" is not sufficient evidence of completion. Before resolving the plan, run the full verification-before-completion checklist: build, type checks, the whole unit/integration suite (to catch regressions outside the new behavior), and any manual checks the plan specifies. TDD proves the new behavior works; verification-before-completion proves nothing else broke.
