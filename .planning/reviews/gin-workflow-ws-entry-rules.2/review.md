# Code Review Ledger

**Bead Status:** `changes-requested`

## Active Lease
*No active lease.*

## Review Approval
*Not approved or approval has been invalidated.*

## Tracked Repositories
### Repository: `gin-workflow`
- **Role:** `primary`
- **Review Ref:** `refs/gin/review/gin-workflow-ws-entry-rules.2`
- **Base SHA:** `6938bf8c26ac5ab6b29c923a1189503c4b87a1d3`
- **Reviewed SHA:** `2cb46cd0df0890659325797a1a2091123dce3173`
- **Source Identity:** `complete`
- **Repository Path:** `.`
- **Checkpoint Ref:** `refs/gin/review/gin-workflow-ws-entry-rules.2`
- **Checkpoint SHA:** `2cb46cd0df0890659325797a1a2091123dce3173`
- **Scope Hash:** `cf81789728b4d008aec9c15c2eeaed4cd381332309c20dfb122bffb24852c6c7`
- **Tree Hash:** `c7363777b7d19a4e87a91a30f8d4124d02cbae1abbbe68db5a42d6ccdc2c7ca4`

## Source Scope Configuration
- **Included Paths:**
- **Excluded Artifact Paths:**
- **Allowed Generated Paths:**

## Findings Summary
| Finding ID | Severity | Status | Clarification Count | Linked Bead |
| :--- | :--- | :--- | :---: | :--- |
| `F1-doctor-crash-on-unreadable-child-manifest` | `IMPORTANT` | `open` | 0 | - |
| `F2-test-gaps-unknown-entry-pack-and-worktree` | `SUGGESTION` | `open` | 0 | - |

## Findings Detail
### `F1-doctor-crash-on-unreadable-child-manifest` (IMPORTANT)
- **Status:** `open`
- **Clarification Count:** 0

### `F2-test-gaps-unknown-entry-pack-and-worktree` (SUGGESTION)
- **Status:** `open`
- **Clarification Count:** 0


## Event Chronology
| Event ID | Timestamp | Action | Actor |
| :--- | :--- | :--- | :--- |
| `EV-000001` | `2026-11-14T09:55:49.893548Z` | `ledger-created` | `implementer:antigravity:worker` (worker) |
| `EV-000002` | `2026-11-14T09:55:50.163965Z` | `source-checkpoint-created` | `implementer:antigravity:worker` (worker) |
| `EV-000003` | `2026-11-14T09:59:25.494758Z` | `review-requested` | `implementer:antigravity:worker` (worker) |
| `EV-000004` | `2026-11-14T10:00:48.416794Z` | `lease-acquired` | `reviewer:claude` (reviewer) |
| `EV-000005` | `2026-11-14T10:00:48.444290Z` | `review-started` | `reviewer:claude` (reviewer) |
| `EV-000006` | `2026-11-14T10:02:03.053601Z` | `finding-created` | `reviewer:claude` (reviewer) |
| `EV-000007` | `2026-11-14T10:02:03.285769Z` | `finding-created` | `reviewer:claude` (reviewer) |
| `EV-000008` | `2026-11-14T10:02:08.365913Z` | `changes-requested` | `reviewer:claude` (reviewer) |
| `EV-000009` | `2026-11-14T10:02:12.588229Z` | `lease-released` | `reviewer:claude` (reviewer) |
