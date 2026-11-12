# Epic kinds

An epic has one kind: `capability`, `technical`, or `parity`. Without a `kind:` label the kind is `capability`.

## Where the kind lives
The kind is the epic's `kind:` label. The spec repeats it on a `Kind:` line, which the gate checks.

Add the line to a technical or parity spec. A capability spec may omit it. A label and a `Kind:` line that disagree, two `kind:` labels, an unknown kind, or an unreadable tracker make `gin` refuse the epic with a message that names the cause.

## Epic without a label
Ask once which kind it is. Then run `gin task update <epic> --add-label kind:<kind>`.

## Capability
Discuss as usual: stories, use cases, and diagrams.

## Technical
Ask technical questions only. Write no user stories, use cases, or activity diagrams.

With the legacy layout, start from `gin specs template technical-design.md`. With `project.layout: sdd`, write `03-design.md`. The `02-spec-delta.md` may be empty or missing, and `01-proposal.md` is then the spec artifact.

## Parity
Read the confirmed `Kind: legacy` asset folders of the behaviour to keep. Write a `Parity with:` line that names them as backticked paths. Ask for, and write, stories or REQs only for the deltas from that behaviour.

## Approval
`team.approvals.requirement_confirmed` may hold one policy per kind. `gin team check --gate requirement_confirmed <url> --workflow-id <epic>` applies the policy of the epic's kind.
