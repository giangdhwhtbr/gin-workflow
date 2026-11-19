# Use case diagram extensions: cross-capability includes, generalization, context diagram

Epic: gin-workflow-16jz
Workflow: gin-workflow-16jz
Kind: capability
Status: confirmed by the user on 2026-11-19.

## Goal and scope

With the SDD layout, use cases live per capability (`<specs>/<cap>/use-cases/<slug>.md`); `Includes:` and `Extends:` name slugs of the same capability only (`specs.lint_references` reports any other value), and `gin specs export` draws one use case diagram per capability (`specs_export.use_case_diagram`). `<specs>/actors.md` (from `gin-workflow-414v`) adds descriptions to the actor catalogue. A BA's SRS also needs a shared use case included across features (Authenticate used by several capabilities), actor and use case generalization (Admin is a User), and a system-level context diagram. Group C of the BA review follow-ups of `gin-workflow-cyb8`.

Confirmed decisions (2026-11-19):

- Actor generalization is declared once per project, in an optional `Is a` column of `<specs>/actors.md`; use case generalization by a `Specializes:` line in the specializing use case.
- The context diagram is generated at export and placed at the start of the Actors section: the system box holds one node per capability; each actor outside connects to the capabilities it takes part in, solid when it is the primary actor of a use case there, dashed when only secondary; actor generalization edges are drawn too.

Assumptions (defaults, not asked):

- `Includes:`, `Extends:`, and `Specializes:` take `slug` (same capability) or `cap/slug` (another capability). An activity diagram's `Use case:` stays same-capability.
- Mermaid flowcharts have no hollow-triangle arrow, so generalization is a thick labelled edge `== is a ==>`.
- A one-capability export draws the context diagram for that capability only.
- Out of scope: `/gin:explain` pages; data flows on the context diagram; the legacy layout.

## Requirements

### R1. Cross-capability references

A value of `Includes:`, `Extends:`, or `Specializes:` is `slug` or `cap/slug`. `lint_references` reports a value that names no use case (`docs/specs/orders/use-cases/pay.md: Includes names unknown use case 'auth/verify-otp'`) or names the file itself, including as `<own cap>/<own slug>`. The use case diagram of a capability draws each use case of another capability that one of its use cases includes, extends, or specializes, inside a dashed `subgraph` titled with that capability's title, with the same edges as within a capability.

### R2. Actor generalization

`<specs>/actors.md` may add an `Is a` column naming another actor (matched like actor names: case and repeated spaces ignored). `lint_actors` reports a parent that is neither in the table nor named by any use case (`docs/specs/actors.md:6: actor 'Admin' is a 'Superuser', which is no actor`) and a cycle (`docs/specs/actors.md: actor generalization cycle: Admin, User`). The use case diagram draws `child == is a ==> parent` for every actor it shows with a parent, adding the parent actor nodes up the chain. The actor catalogue (`specs_matter.actors`, SRS Actors table) gains an `is_a` value and an "Is a" column.

### R3. Use case generalization

A use case may add `Specializes: <slug | cap/slug>`. `lint_references` reports an unknown or self target as in R1, and `lint_use_cases` reports a cycle across specializations (`docs/specs/auth/use-cases/a.md: use case generalization cycle: auth/a, auth/b`). The use case diagram draws `child == is a ==> parent`.

### R4. Context diagram

`specs_export.context_diagram(capabilities, rows)` builds a Mermaid `flowchart LR`: `subgraph system[<document title>]` with one node per exported capability (its title), the actors outside (one node per actor, styled like the use case diagram's actors), an edge from each actor to each capability where it is the primary actor of a use case (`-->`), a dashed edge (`-.->`) where it is only a secondary actor there, and `== is a ==>` edges between actors. The SRS Actors section starts with it, in `<section class="context-diagram" id="context-diagram">`, before the actor catalogue table; with no use case at all there is no diagram. A one-capability export limits it to that capability and its actors.

### R5. Template and documentation

- `templates/use-case.md` comment: `cap/slug` for another capability, and the optional `Specializes:` line (no `--` inside the comment).
- `docs/guides/sdd.md`, `docs/guides/ba.md` and their `.vi.md` versions: cross-capability references, the `Is a` column, `Specializes:`, the context diagram.
- `docs/reference/cli.md`: the new lint findings and the export's context diagram.

## User Stories

### US-1: Share a use case across capabilities
As a business analyst, I want a use case of one capability to include a use case of another, so that a shared step such as Authenticate is written once.

Acceptance criteria:
- `Includes: auth/sign-in` in `orders/use-cases/pay.md` passes `specs lint` when `auth/use-cases/sign-in.md` exists, and fails naming the reference when it does not.
- The orders use case diagram shows Sign in in a dashed Auth subgraph, joined to Pay by an `«include»` edge.
- `Includes: orders/pay` inside `orders/use-cases/pay.md` fails as a self reference.

### US-2: Show who is a kind of whom
As a business analyst, I want to declare that Admin is a User and that one use case specializes another, so that the diagrams show the hierarchy the customer expects.

Acceptance criteria:
- With `| Admin | Manages users | User |` in `actors.md`, a diagram showing Admin also shows User and an `is a` edge from Admin to User; the Actors table shows "User" in its "Is a" column.
- `Is a` naming no actor, and Admin is a User with User is an Admin, each fail `specs lint`.
- `Specializes: sign-in` in `sign-in-sso.md` draws an `is a` edge to Sign in; two use cases specializing each other fail `specs lint`.
- Use cases and an `actors.md` without these lines lint and export as before.

### US-3: See the whole system at a glance
As a customer, I want a context diagram at the start of the Actors section, so that I see every actor and the capabilities each one uses before reading the details.

Acceptance criteria:
- `gin specs export --all` with two capabilities shows a `context-diagram` section before the actor table: a system subgraph with both capability nodes, each actor connected by a solid edge where it is a primary actor and a dashed edge where it is only secondary.
- `export <cap>` shows only that capability and its actors.
- Without any use case there is no context diagram section.

## Errors and compatibility

- Existing use cases and `actors.md` files hold none of the new forms and lint and export unchanged, except that the SRS Actors section gains the context diagram.
- Lint findings exit 1, as other lint findings do.
- `dist/` is regenerated by the build; no hand edits there.

## Testing

- `tests/workflow_core/test_specs.py`: `cap/slug` known, unknown, and self for Includes/Extends/Specializes; actor `Is a` unknown and cycle; use case specialization cycle; files without the new forms unchanged.
- `tests/workflow_core/test_specs_matter.py`: `is_a` in actor rows.
- `tests/workflow_core/test_specs_export.py`: cross-capability subgraph and edges; actor and use case `is a` edges with parent nodes added; context diagram nodes, solid and dashed edges, one-capability filtering, no section without use cases; existing diagram outputs unchanged.
- A browser render of an exported SRS with each new element; `gin docs check`; full suite through the pre-push hook.

## Open Technical Questions
