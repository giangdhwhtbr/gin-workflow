# Bead attachments

Epic: gin-workflow-s6fv
Kind: capability
Status: confirmed by the user on 2026-11-21.

## Goal and scope

A bead can carry images that every member and gin-console can see. Today gin-qa bug beads list their evidence as local paths under the gitignored `qa/evidence/` (`gin_qa/bugs.py:82-91` writes each `--evidence` value as a `- <item>` line), so only the tester's machine shows the screenshots. Beads already sync between machines through the Dolt remote; the images do not.

gin-workflow gains `gin attach`, which puts an image in a shared store and records it in the bead's `metadata.attachments`. gin-qa uses it when it files a bug. gin-console reads the store in its own epic, `gin-console-rm-shared-attachments`, which depends on `external:gin-workflow:bead-attachments`.

Decided in discuss (2026-11-21):

- The default store is `git-ref`: one ref, `refs/gin/attachments`, in the project repository, pushed to `origin`. `local` and `s3` are the other stores; `s3` uses boto3 as an optional dependency.
- Any bead can carry attachments; gin-qa is one caller.
- `gin attach prune` removes blobs no bead references, and blobs of beads closed longer than `attachments.retention_days` ago. Unset `retention_days` keeps them. It is a dry run unless `--apply` is given.
- gin-qa `cases bug` attaches its `--evidence` image files and the screenshots of the failed steps of the case's e2e run.

In scope: the `gin attach` command, the three stores, the `attachments` config section, EXIF removal, the gin-qa `cases bug` change, and the docs.

Out of scope:

- gin-console reading and showing attachments (`gin-console-rm-shared-attachments`), and uploading from the console.
- Files other than PNG, JPEG, WebP, and GIF.
- Public or presigned URLs.
- `gin-qa e2e run` filing bugs by itself.

## Requirements

1. `gin attach add <bead> <file>... [--caption TEXT] [--case ID] [--step N] [--format text|json]` adds each file to the bead:
   - It accepts PNG, JPEG, WebP, and GIF, recognised by their magic bytes, not their file name.
   - It refuses a file larger than `attachments.max_bytes` (default 10 MiB) after EXIF removal.
   - It removes EXIF and XMP metadata from JPEG (APP1 segments), PNG (`eXIf`, `tEXt`, `zTXt`, `iTXt` chunks), and WebP (`EXIF` and `XMP ` chunks, and their flags in `VP8X`). A GIF is stored unchanged.
   - It hashes the cleaned bytes with sha256, puts them in the configured store, and appends `{sha256, name, mime, bytes, caption, case, step, added_by, added_at, store, path}` to the bead's `metadata.attachments`. `added_by` is the git `user.email`; `path` is the blob's location in the store.
   - It prints `![<caption or name>](attachment:<sha256>)` per file; JSON output lists the entries.
   - A file whose sha256 the bead already holds adds no second entry and prints the existing reference.
2. `gin attach list <bead> [--format text|json]` prints the bead's entries.
3. `gin attach fetch [--bead ID --out DIR]` brings the local copy of the store up to date (`git-ref`: fetch origin's ref into `refs/gin/attachments-origin` and merge it into `refs/gin/attachments`, keeping blobs not yet pushed). With `--bead` and `--out`, it writes each of the bead's files to `DIR/<sha256>.<ext>` after checking its sha256. A read-only reader that never runs `gin attach add` may fetch `+refs/gin/attachments:refs/gin/attachments` directly; any other clone runs `gin attach fetch`, because that forced fetch drops unpushed blobs.
4. `gin attach push` sends local store commits that a failed `add` left unpushed (`git-ref` only; other stores print that nothing is pending).
5. `gin attach prune [--apply] [--format text|json]` lists, then with `--apply` removes:
   - blobs that no bead's `metadata.attachments` references;
   - blobs whose beads are all closed and whose newest `closed_at` is more than `attachments.retention_days` ago.
   A removed blob's entries stay on their beads and gain `pruned_at`. `git-ref` writes one new root commit that holds the kept blobs and pushes it with `--force-with-lease`.
6. The `git-ref` store:
   - Blob path in the tree: `<first two hex digits>/<sha256>`.
   - `add` fetches the ref from `origin`, writes a commit on top of it through a temporary index, as the review ledger's git adapter does (`review_ledger/git_adapter.py`), and pushes it without force. A rejected push fetches again and rebuilds the commit, up to 3 attempts.
   - Without an `origin` remote, the store works locally and `add` warns that the files are not shared.
7. The `local` store keeps blobs under `<main checkout>/.agent-workflow/attachments/<aa>/<sha256>`, which setup gitignores.
8. The `s3` store:
   - Puts each blob at `<prefix>/<aa>/<sha256>` in `attachments.s3.bucket`, with `endpoint_url` and `region` from config for R2 and MinIO.
   - Credentials come from boto3's default chain (environment, shared credentials file, instance role); the config holds none.
   - boto3 loads through `require_boto3()`, built like `require_yaml()` (`configuration.py:85-93`), so it is needed only with `store: s3`.
   - It never creates a public object, an ACL, or a presigned URL.
9. Config section `attachments`: `store` (`git-ref`, `local`, or `s3`; default `git-ref`), `max_bytes` (integer, minimum 1, default 10485760), `retention_days` (integer, minimum 1, optional), and `s3` (`bucket` required with `store: s3`, `prefix`, `endpoint_url`, `region`). The schema version stays 2.11; the docs say the section needs the gin release that ships it (assumed 3.5.0); older versions accept the key (the top-level schema allows unknown keys) and ignore it.
10. gin-qa `cases bug`:
    - Once it knows the bug id (a new bug, or the case's open bug that gets a re-run note), it attaches each `--evidence` value that names an image file, and the screenshot of each `failed` step in `<evidence root>/<Run>/<tc>/result.json` when the case's `Run` is an e2e run folder.
    - A new bug's `## Evidence` lists each attached image as `- ![<tc> step <n>: <title>](attachment:<sha256>)` followed by `  local: <path>`; other evidence values stay as they are.
    - The one-line re-run note lists `attachment:<sha256>` values after `Evidence:`.
    - A failed attach prints a warning and keeps the local path line; the bug is still filed.

## User Stories

### US-1: Attach a screenshot to a bead
As a developer or tester, I want to attach an image to a bead with one command, so that the screenshot travels with the bead.

Acceptance criteria:
- `gin attach add <bead> shot.png --caption "Empty cart"` prints `![Empty cart](attachment:<sha256>)` and exits 0.
- `gin task show <bead> --json` then holds one `metadata.attachments` entry with that sha256, `mime` `image/png`, and the caption.
- Adding the same file again leaves one entry.
- A `.png` file that holds a PDF is refused with exit 1 and the reason; the other files of the same call are still added.
- A JPEG with GPS EXIF is stored without its APP1 Exif segment, and the stored sha256 is that of the cleaned bytes.

### US-2: See attachments on another machine
As a teammate on another machine, I want the images attached elsewhere to reach my checkout, so that I can open them.

Acceptance criteria:
- After machine A runs `gin attach add`, machine B runs `bd dolt pull` and `gin attach fetch --bead <id> --out out/`, and `out/` holds each file with the sha256 of its entry.
- Two machines that add different files at the same time both succeed, and the ref on `origin` holds both blobs.

### US-3: Read attachments from a tool
As a reader such as gin-console, I want a stable listing and blob location, so that I can show the images without guessing.

Acceptance criteria:
- `gin attach list <bead> --format json` prints the entries with `sha256`, `mime`, `bytes`, `caption`, `store`, and `path`.
- In the `git-ref` store, `git cat-file blob refs/gin/attachments:<path>` returns bytes whose sha256 is the entry's.
- The docs name the refspec and the tree layout.

### US-4: Choose where attachments live
As a project maintainer, I want to pick the store, so that the images live where my team already has access.

Acceptance criteria:
- With no `attachments` section, `gin attach add` uses `git-ref`.
- With `store: local`, the blob lands under `.agent-workflow/attachments/` and nothing is pushed.
- With `store: s3` and boto3 missing, `gin attach add` exits 2 with the pip command to install it.
- With `store: s3` and a bucket, the blob is put at `<prefix>/<aa>/<sha256>` without an ACL, and no command prints a URL.

### US-5: Remove old attachments
As a project maintainer, I want to remove attachments nobody needs, so that the store stops growing.

Acceptance criteria:
- `gin attach prune` lists the orphan blobs and the blobs of beads closed more than `retention_days` ago, and changes nothing.
- `gin attach prune --apply` removes them; their entries gain `pruned_at`, and a blob still referenced by an open bead stays.
- Without `retention_days`, only orphans are listed.

### US-6: File a bug with its screenshots
As a tester, I want `gin-qa cases bug` to attach the failing screenshots, so that the developer sees them on any machine.

Acceptance criteria:
- For a case whose `Run` is an e2e run with one failed step, the new bug's `## Evidence` shows that step's screenshot as an `attachment:` reference with its local path below it.
- An `--evidence` value that names a PNG file becomes an `attachment:` reference; a value that is not a file stays a plain line.
- When attaching fails, the bug is still created with the local paths and the command prints a warning.

### US-7: Finish an upload that failed
As a developer working offline, I want to push the attachments later, so that a lost connection does not lose them.

Acceptance criteria:
- When the push fails, `gin attach add` keeps the entry, exits 0, and warns to run `gin attach push`.
- `gin attach push` later sends the commit, and a fetch on another machine sees the blob.

## Errors and compatibility

- Exit codes: 0 ok; 1 at least one file refused (type or size); 2 a usage error, a missing bead, a missing tracker, a configuration error, or a store that cannot be reached for a read.
- `metadata.attachments` is read, extended, and written back with `bd update --set-metadata`, like `milestone_moves` (`milestone_cli.py`). Two writers on one bead at the same moment can lose one entry; its blob then shows as an orphan in `prune`.
- The markdown task backend has no metadata: `gin attach` exits 2 and says it needs Beads.
- gin runs git and bd with list arguments and no shell, so paths with spaces work on Windows. Blob paths in the store always use `/`.
- Secrets never enter config: the S3 keys are only `bucket`, `prefix`, `endpoint_url`, and `region`.
- Configs without `attachments` behave as before; a config with it needs the gin release that ships this epic.

## Testing

- Type and cleaning: fixture bytes for each format, including a JPEG with an Exif APP1 segment, a PNG with `eXIf` and `tEXt` chunks, a WebP with `EXIF` and the `VP8X` flag, a GIF, and a mislabelled file.
- `git-ref` store: a temporary bare repository as `origin` and two clones; concurrent `add` from both clones; `fetch`, `push` after a failed push, and `prune --apply` with `--force-with-lease`.
- `local` store, and `s3` with a stub client injected in place of boto3 (no network); `require_boto3()` without boto3.
- CLI: text and JSON output, exit codes, idempotent `add`, and a bead on the markdown backend, with a fake `bd`.
- gin-qa: `cases bug` against an e2e run fixture with one failed step, a plain `--evidence` value, and a failing attach.
- Config: schema accepts the section and rejects an unknown store; docs check for the new pages.
- Windows: the existing Windows CI job.

## Open Technical Questions
