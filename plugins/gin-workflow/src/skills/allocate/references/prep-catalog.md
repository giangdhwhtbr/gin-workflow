# Prep catalog

A prep task is pre-discuss work under a roadmap epic. It carries the labels `prep` and `prep:<type>`, and neither `track:` nor `req:`; a bead with either of those is a track, not a prep task.

| Type | Default role | Proposed when | Done when |
|---|---|---|---|
| `capture` | `ba` | SDD layout only. A `parity` epic, or a `capability` epic whose `Scope:` or `Evidence:` names existing behaviour, and the capability has no confirmed legacy capture. | A confirmed legacy capture exists; the close reason names its folder. |
| `mockup` | `ba` | SDD layout only. A `capability` epic whose scope includes new screens, and the capability has no confirmed mockup. | A confirmed mockup exists; the close reason names its folder. |
| `spike` | A member holding the lead role `team.areas.<area>.lead` of the area named in `Tracks:`; else a member whose role ends in `_lead`. | A `technical` epic, an epic with `Complexity: high`, or a technical risk in `Risks:`. | With Beads, the epic has the comment `[gin answer] <prep-id>: <finding>`; with the markdown backend, the close reason holds the finding. |
| `question` | `pm`, or `ba` for a business-rule question. | Each open business question in `Risks:` or the description. | With Beads, the epic has the comment `[gin answer] <prep-id>: <answer>`; with the markdown backend, the close reason holds the answer. |
| `other` | Chosen by the lead. | The lead adds it. | As the lead writes it. |

## Confirmed asset folder

A confirmed asset folder is `<specs>/<cap>/assets/<YYYY-MM-DD>/` whose `description.md` has a `Confirmed: <date>` line. It is a legacy capture when that file also has `Kind: legacy`, and a mockup when the folder holds `mockup/index.html`.
