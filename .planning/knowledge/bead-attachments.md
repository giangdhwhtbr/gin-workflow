# Bead attachments: gin attach, three stores, and gin-qa screenshots

**Context**
Epic `gin-workflow-s6fv` (2026-11-21, spec `.planning/specs/2026-11-21-bead-attachments-design.md`). gin-qa bug beads listed their screenshots as gitignored local paths, so other machines and gin-console could not see them. gin-console's epic `gin-console-rm-shared-attachments` depends on `external:gin-workflow:bead-attachments` for the read side.

**Decision/Solution**
- `gin attach {add,list,fetch,push,prune}` (`workflow_core/attach_cli.py`, `attachments.py`). Images are recognised by magic bytes (PNG, JPEG, WebP, GIF), EXIF and XMP are removed with the stdlib (`attach_images.py`), and the cleaned bytes are hashed with sha256. Each bead lists its images in `metadata.attachments`; a pruned entry keeps its row and gains `pruned_at`.
- Every store path is `<aa>/<sha256>` and is checked by `attach_store.check_path` before any read, write, or delete, because paths come from bead metadata or a fetched store.
- `git-ref` (default) keeps one commit history on `refs/gin/attachments` and the last seen remote tip on `refs/gin/attachments-origin`. A merge keeps origin's blobs plus the blobs this clone added since it last saw origin, with origin's tip as the only parent; `put` of a blob that origin pruned writes an `attach <sha>` marker so the merge keeps it. A path missing from origin counts as pruned only when origin's history has a parentless `prune attachments` commit the clone has not seen. `push` retries 3 times; `prune` writes a new root and pushes with `--force-with-lease=<ref>:<seen>` and no `+`. A writer clone runs `gin attach fetch`; only a read-only reader may fetch `+refs/gin/attachments:refs/gin/attachments`.
- `s3` loads boto3 through `require_boto3()` only when chosen; credentials come from boto3's default chain, never config; no ACL or presigned URL; per-key `Errors` of `delete_objects` raise.
- `prune` stops when any bead's `metadata.attachments` is unreadable or an entry has no usable path, takes candidates only from the store's own paths, and keeps any path an open bead references; the newest `closed_at` of the referencing beads decides retention.
- `gin-qa cases bug` attaches image `--evidence` files inside the repository and the failed-step screenshots of the case's e2e run, rewrites the bug description once, and turns every attach problem into a warning.
- An older gin ignores the `attachments` config section instead of rejecting it: the top-level config schema allows unknown keys (`additionalProperties: True`).

**Consequences**
- Plan code for concurrency and binary formats was a starting point, not proof: review found a `struct.error` on short WebP input, a lost re-attach after a prune, and a merge that would undo every prune. Give such tracks the strongest route and a mutation check in review.
- `git commit-tree` needs `GIT_AUTHOR_*`/`GIT_COMMITTER_*` when no identity is configured and has ignored `commit.gpgSign` since git 2.9. Tests isolate identity with `GIT_CONFIG_GLOBAL=<empty file>` and `GIT_CONFIG_NOSYSTEM=1`.
- `--force-with-lease=<ref>:<expect>` alone allows the rewrite only while the remote is at `<expect>` (empty means absent); a `+` refspec bypasses the lease.
- A fetch that moves a tracking ref must put it back when the merge after it fails, or the next merge uses the wrong base.
- `fetch --no-write-fetch-head` needs git 2.29 or later. Attachment pushes run the repository's pre-push hooks; gin passes no `--no-verify`.
- A new name in `TOP_COMMANDS` needs a `## \`gin <name>\`` heading in `docs/reference/cli.md` (`test_docs_coverage.py`). A new `LOCAL_GITIGNORE_ENTRIES` item needs the two exact lists in `test_setup_cli.py`.
- `tasks.backend(root)` is `markdown` until `.agent-workflow/generated/effective-config.yaml` exists, so tests that need the real bd write the config with `providers.task_tracking: beads` and resolve it.
- Orphan prune trusts that every machine has pushed its beads: run `bd dolt pull` first; the dry run says so.

**References**
- `plugins/gin-workflow/src/scripts/workflow_core/{attach_images,attach_store,attach_gitref,attach_s3,attachments,attach_cli}.py`, `schemas.py` (`attachments`), `setup_service.py` (`LOCAL_GITIGNORE_ENTRIES`); `plugins/gin-qa/src/scripts/gin_qa/bugs.py`
- Tests: `tests/workflow_core/test_attach_*.py`, `test_attachments*.py`, `tests/gin_qa/test_cases_bug.py`
- Docs: `docs/reference/cli.md` (`gin attach`, `gin-qa cases bug`), `docs/reference/config.md` (`attachments`)
- Beads: `gin-workflow-s6fv`, `gin-console-rm-shared-attachments`
- Related: [qa-evidence](qa-evidence.md)

**Scope**
Bead attachments, their stores and config, and gin-qa bug screenshots.
