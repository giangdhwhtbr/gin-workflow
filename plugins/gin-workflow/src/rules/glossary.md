---
id: glossary
tier: framework
applies_to: ["**/*"]
detect: {files_exist: [.planning/codebase/11-GLOSSARY.md, docs/codebase/11-GLOSSARY.md]}
---
- [critical] `glossary-names`: Name business concepts in identifiers, UI text, and docs with the `English` of their `confirmed` row in `11-GLOSSARY.md` of the codebase docs folder (`.planning/codebase/`, or `docs/codebase/` with the SDD layout).
- [high] `glossary-gaps`: When a concept has no row or only a `proposed` one, use the name the spec or plan gives and report the term in the handoff; do not edit the glossary.

## Why
- `glossary-names`: A legacy concept must keep one English name across every epic of the new application.
- `glossary-gaps`: Only the user confirms a translation, and the glossary is outside the task scope.
