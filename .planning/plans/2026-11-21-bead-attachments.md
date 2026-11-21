# Plan: Bead attachments

Epic: gin-workflow-s6fv
Spec: `.planning/specs/2026-11-21-bead-attachments-design.md`

## Objective

`gin attach add` puts a cleaned image in a shared store and records it in the bead's `metadata.attachments`; `list`, `fetch`, `push`, and `prune` read, sync, and trim the store. The store is `git-ref` by default (`refs/gin/attachments` pushed to `origin`), or `local`, or `s3` with boto3 installed. `gin-qa cases bug` attaches its image evidence and the screenshots of the failed e2e steps. The docs describe the command, the config section, and the store layout a reader such as gin-console needs. The full suite passes.

## Global Constraints

From the spec:

- Default store `git-ref`, one ref `refs/gin/attachments`, blob path `<first two hex digits>/<sha256>`; `local` keeps blobs under `<main checkout>/.agent-workflow/attachments/`; `s3` keeps them at `<prefix>/<aa>/<sha256>`.
- Accepted types: PNG, JPEG, WebP, GIF by magic bytes. EXIF and XMP are removed before hashing (JPEG APP1; PNG `eXIf`, `tEXt`, `zTXt`, `iTXt`; WebP `EXIF`, `XMP ` and their `VP8X` flags). GIF is stored unchanged.
- `metadata.attachments` entry: `{sha256, name, mime, bytes, caption, case, step, added_by, added_at, store, path}`, plus `pruned_at` after prune. Any bead may carry attachments.
- No public object, ACL, or presigned URL. S3 credentials come from boto3's default chain; config holds only `bucket`, `prefix`, `endpoint_url`, `region`.
- Config schema stays 2.11; the docs say `attachments` needs gin 3.5.0 or later.
- Exit codes: 0 ok; 1 at least one file refused; 2 usage, missing bead, missing tracker, configuration, or a store that cannot be reached.
- Out of scope: gin-console reading and showing attachments, uploads from the console, non-image files, public URLs, `gin-qa e2e run` filing bugs.

Added by this plan:

- Tracks run in order; each leaves the tests it names green, and Track 5 and Track 7 run the full suite.
- New modules sit flat in `workflow_core/`, named `attach_*.py` and `attachments.py`, like `team_*.py` and `milestone*.py`.
- Tests that call the real `bd` carry `@unittest.skipUnless(shutil.which("bd"), "bd is not installed")`; the release runner has no `bd`.
- Tests that use git create their own repositories under `tempfile.TemporaryDirectory()` and never touch this checkout's refs.
- No track bumps the version, runs `./install.sh` against the real `HOME`, `gin setup update`, or `gin setup refresh`.
- Read a pytest summary line before calling a run green: `N passed`, no `failed`, no `error`.

## Route Rubric
- Choose the weakest model that can do the work.
- Raise the model for broad context or design judgement.
- Raise the effort for intrinsic difficulty: intricate logic, many edge cases, or long chains of steps.

| Kind of work | Model | Effort |
|---|---|---|
| Mechanical edits, documentation, boilerplate | weakest | `low` |
| Bounded implementation with a clear spec | middle | `medium` |
| Cross-module change, security, migration, concurrency | strongest | `high` |

Unclear requirements never raise the model or effort.

## Requirement Analysis
- Problem statement: gin-qa bug beads point at gitignored local screenshots, so other machines and gin-console cannot see them.
- Success criteria: the spec's user stories US-1 to US-7 and its Testing section.
- Constraints: Global Constraints above.
- Non-goals: the out-of-scope list above.

## Approach Options
### Option 1: One ref with commit history (confirmed at discuss)
- Summary: `refs/gin/attachments` holds a commit whose tree has every blob; `add` commits locally, `push` merges the remote tip by tree union and pushes fast-forward, retrying up to 3 times; `prune` writes a new root commit and pushes with `--force-with-lease`.
- Pros: one ref to fetch; the name gin-console's roadmap already uses; content-addressed paths never conflict.
- Cons: prune rewrites the ref.

### Option 2: One ref per attachment
- Summary: `refs/gin/attachments/<sha256>`, one per blob.
- Pros: no push race; prune deletes refs.
- Cons: thousands of refs; readers fetch by glob. Rejected at discuss.

### Recommended Approach
- Selected option: Option 1.
- Rationale: confirmed by the user on 2026-11-21.

## Scope
- In scope: spec requirements 1 to 10.
- Out of scope: the Global Constraints' out-of-scope list.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Each track builds on the interfaces of the previous one (store protocol, settings, add), and Tracks 5 to 7 share attachments.py and attach_cli.py.
```

## Interfaces

Produced by Tracks 1 to 6 and consumed later; names and types are fixed here.

```python
# workflow_core/attach_images.py (Track 1)
EXTENSIONS: dict[str, str]  # {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/gif": "gif"}
def sniff(data: bytes) -> str | None: ...          # MIME type from magic bytes, None for anything else
def clean(data: bytes, mime: str) -> bytes: ...    # without EXIF/XMP; ValueError when the structure is broken

# workflow_core/attach_store.py (Track 2)
class StoreError(Exception): ...                    # a store that cannot be read or written (exit 2)
def blob_path(sha256: str) -> str: ...             # f"{sha256[:2]}/{sha256}"
class Store(Protocol):
    name: str                                       # "git-ref", "local" or "s3"
    def put(self, sha256: str, data: bytes) -> str: ...   # store path; idempotent
    def get(self, path: str) -> bytes: ...                # StoreError when missing
    def paths(self) -> set[str]: ...                      # every blob path in the local view of the store
    def remove(self, paths: Collection[str]) -> None: ...
    def push(self) -> str | None: ...                     # None when nothing is pending, else a warning
    def fetch(self) -> None: ...
class LocalStore:                                   # name "local"; LocalStore(directory: Path)

# workflow_core/attach_gitref.py (Track 3)
REF = "refs/gin/attachments"
REMOTE_REF = "refs/gin/attachments-origin"         # last fetched tip of the remote
class GitRefStore:                                  # name "git-ref"; GitRefStore(repo: Path, remote: str = "origin")

# workflow_core/attach_s3.py (Track 4)
def require_boto3(): ...                            # DependencyUnavailableError with the pip command
class S3Store:                                      # name "s3"; S3Store(bucket, prefix="", endpoint_url=None, region=None, client=None)

# workflow_core/attachments.py (Tracks 2, 5, 6)
SCHEME = "attachment:"
DEFAULT_MAX_BYTES = 10 * 1024 * 1024
class AttachmentError(Exception): code: int        # 2 unless given
@dataclass(frozen=True)
class Settings:
    store: str = "git-ref"; max_bytes: int = DEFAULT_MAX_BYTES; retention_days: int | None = None
    s3: Mapping[str, str] = field(default_factory=dict)
def load_settings(repo: Path) -> Settings: ...      # from the main checkout's effective config
def open_store(repo: Path, settings: Settings) -> Store: ...
def entries(row: Mapping[str, Any]) -> list[dict[str, Any]]: ...   # metadata.attachments, str or list
def reference(entry: Mapping[str, Any]) -> str: ...  # "![<caption or name>](attachment:<sha256>)"
@dataclass
class Added:
    entries: list[dict[str, Any]]; refused: list[dict[str, str]]; warning: str | None
def add(repo: Path, bead: str, files: Sequence[Path], *, caption: str | None = None, case: str | None = None,
        step: int | None = None, now: datetime | None = None, store: Store | None = None) -> Added: ...
def list_entries(repo: Path, bead: str) -> list[dict[str, Any]]: ...
def fetch(repo: Path, *, bead: str | None = None, out: Path | None = None, store: Store | None = None) -> list[Path]: ...
def push(repo: Path, *, store: Store | None = None) -> str | None: ...
def prune(repo: Path, *, apply: bool = False, now: datetime | None = None, store: Store | None = None) -> dict[str, Any]: ...

# workflow_core/attach_cli.py (Tracks 5, 6)
def main(argv: Sequence[str]) -> int: ...           # gin attach {add,list,fetch,push,prune}
```

## Tasks

### Track 1: Image types and metadata removal
- **Dependencies**: none
- **Files**:
  - Create `plugins/gin-workflow/src/scripts/workflow_core/attach_images.py`
  - Test `tests/workflow_core/test_attach_images.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** pure byte parsing with a clear format per type; edge cases are listed below.
- **Steps**:
  1. Write `tests/workflow_core/test_attach_images.py`. Build the fixtures in the test module from bytes:
     - `png(*chunks)`: `b"\x89PNG\r\n\x1a\n"` then each `(kind, data)` as `struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))`, with `IHDR` (13 bytes), `eXIf`, `tEXt`, `IDAT`, `IEND`.
     - `jpeg(*segments)`: `b"\xff\xd8"`, each `(marker, payload)` as `b"\xff" + bytes([marker]) + struct.pack(">H", len(payload) + 2) + payload`, then `b"\xff\xda" + b"\x00\x08scandata" + b"\xff\xd9"`; segments APP0 `JFIF\x00...`, APP1 `Exif\x00\x00GPS...`, APP1 XMP `http://ns.adobe.com/xap/1.0/\x00...`, DQT.
     - `webp(*chunks)`: `RIFF` + size + `WEBP` + chunks `(fourcc, data)` with a pad byte when the length is odd; `VP8X` with flags `0x0C | 0x10` in byte 0, `EXIF`, `XMP `, `VP8L`.
     - `gif = b"GIF89a" + bytes(7) + b";"`.
     Tests:
     - `sniff` returns `image/png`, `image/jpeg`, `image/webp`, `image/gif` for the four fixtures, and `None` for `b"%PDF-1.7"`, for `b""`, and for `b"RIFF\x00\x00\x00\x00WAVE"`.
     - `clean(png)` drops `eXIf` and `tEXt`, keeps `IHDR`, `IDAT`, `IEND` in order, and stops at `IEND` (trailing bytes dropped).
     - `clean(jpeg)` drops both APP1 segments, keeps APP0, DQT, and the scan data byte for byte; a fill byte `0xFF` before a marker is skipped.
     - `clean(webp)` drops `EXIF` and `XMP `, clears bits `0x0C` of the `VP8X` flags and keeps `0x10`, and the RIFF size equals `len(result) - 8`.
     - `clean(gif, "image/gif") == gif`.
     - Truncated PNG, JPEG without `0xFFDA`, and a WebP whose chunk runs past the RIFF size each raise `ValueError`.
  2. Run `timeout 300 python3 -m pytest tests/workflow_core/test_attach_images.py -q`: fails (module missing).
  3. Create `attach_images.py`:
     ```python
     """The image types gin attach accepts, by magic bytes, and EXIF/XMP removal before hashing."""

     from __future__ import annotations

     import struct

     EXTENSIONS = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/gif": "gif"}
     _PNG = b"\x89PNG\r\n\x1a\n"
     _PNG_DROP = {b"eXIf", b"tEXt", b"zTXt", b"iTXt"}
     _WEBP_DROP = {b"EXIF", b"XMP "}
     _VP8X_EXIF_XMP = 0x08 | 0x04


     def sniff(data: bytes) -> str | None:
         if data.startswith(_PNG):
             return "image/png"
         if data.startswith(b"\xff\xd8\xff"):
             return "image/jpeg"
         if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
             return "image/webp"
         if data[:6] in (b"GIF87a", b"GIF89a"):
             return "image/gif"
         return None


     def clean(data: bytes, mime: str) -> bytes:
         """`data` without EXIF and XMP metadata; ValueError when its structure is broken."""
         if mime == "image/png":
             return _png(data)
         if mime == "image/jpeg":
             return _jpeg(data)
         if mime == "image/webp":
             return _webp(data)
         return data


     def _png(data: bytes) -> bytes:
         out, at = [_PNG], len(_PNG)
         while at < len(data):
             if at + 12 > len(data):
                 raise ValueError("truncated PNG chunk")
             length, kind = struct.unpack(">I4s", data[at:at + 8])
             end = at + 12 + length
             if end > len(data):
                 raise ValueError("truncated PNG chunk")
             if kind not in _PNG_DROP:
                 out.append(data[at:end])
             at = end
             if kind == b"IEND":
                 return b"".join(out)
         raise ValueError("PNG without IEND")


     def _jpeg(data: bytes) -> bytes:
         out, at = [data[:2]], 2
         while at + 1 < len(data):
             if data[at] != 0xFF:
                 raise ValueError("JPEG marker expected")
             marker = data[at + 1]
             if marker == 0xFF:  # fill byte
                 at += 1
                 continue
             if marker == 0xDA:  # start of scan: the rest is image data
                 out.append(data[at:])
                 return b"".join(out)
             if marker == 0x01 or 0xD0 <= marker <= 0xD7:  # markers without a length
                 out.append(data[at:at + 2])
                 at += 2
                 continue
             if at + 4 > len(data):
                 raise ValueError("truncated JPEG segment")
             end = at + 2 + struct.unpack(">H", data[at + 2:at + 4])[0]
             if end > len(data):
                 raise ValueError("truncated JPEG segment")
             if marker != 0xE1:  # APP1 holds Exif and XMP
                 out.append(data[at:end])
             at = end
         raise ValueError("JPEG without image data")


     def _webp(data: bytes) -> bytes:
         end = 8 + struct.unpack("<I", data[4:8])[0]
         if end > len(data) or end < 12:
             raise ValueError("truncated WebP")
         chunks, at = [], 12
         while at < end:
             if at + 8 > end:
                 raise ValueError("truncated WebP chunk")
             kind, length = data[at:at + 4], struct.unpack("<I", data[at + 4:at + 8])[0]
             stop = at + 8 + length + (length & 1)
             if stop > end:
                 raise ValueError("truncated WebP chunk")
             if kind not in _WEBP_DROP:
                 chunk = bytearray(data[at:stop])
                 if kind == b"VP8X" and length:
                     chunk[8] &= ~_VP8X_EXIF_XMP & 0xFF
                 chunks.append(bytes(chunk))
             at = stop
         body = b"WEBP" + b"".join(chunks)
         return b"RIFF" + struct.pack("<I", len(body)) + body
     ```
  4. Run the test: passes.
  5. Commit: `feat(attach): image types by magic bytes and EXIF/XMP removal (gin-workflow-s6fv)`.
- **Acceptance criteria**: the four types are recognised by bytes only; cleaned PNG, JPEG, and WebP hold no EXIF or XMP; broken input raises `ValueError`; the test passes.
- **Estimated complexity**: medium

### Track 2: Store protocol, local store, and the attachments config section
- **Dependencies**: Track 1
- **Files**:
  - Create `plugins/gin-workflow/src/scripts/workflow_core/attach_store.py`
  - Create `plugins/gin-workflow/src/scripts/workflow_core/attachments.py` (settings and store choice only)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/schemas.py:278-282` (new `attachments` section beside `usage`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/setup_service.py:119-126` (`LOCAL_GITIGNORE_ENTRIES` gains `attachments/`)
  - Test `tests/workflow_core/test_attach_store.py`
  - Test `tests/workflow_core/test_attachments_settings.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** a small protocol, a filesystem store, and a schema section that follow existing patterns.
- **Steps**:
  1. Tests:
     - `test_attach_store.py`: `blob_path("ab" + "0" * 62) == "ab/ab" + "0" * 62`. `LocalStore(tmp)`: `put` writes `<tmp>/<aa>/<sha>` and returns `blob_path(sha)`; a second `put` of the same sha leaves the file unchanged; `get` returns the bytes; `get` of a missing path raises `StoreError`; `paths()` lists the stored paths; `remove([path])` deletes the file and an empty `<aa>` folder; `push()` returns `None`; `fetch()` returns `None`; `name == "local"`. `put` writes through a temporary file in the same folder and `os.replace`.
     - `test_attachments_settings.py` (temporary repository with `.agent-workflow/config.yaml`, schema 2.11 config as in `test_migrations.py`): no section gives `Settings()`; `attachments: {store: local, max_bytes: 5, retention_days: 30}` is read back; `store: s3` without `s3.bucket` raises `AttachmentError` naming `attachments.s3.bucket`; `store: ftp` fails schema validation (`ConfigValidationError`); `open_store(repo, Settings(store="local"))` is a `LocalStore` on `<main checkout>/.agent-workflow/attachments`; `setup_service.LOCAL_GITIGNORE_ENTRIES` contains `"attachments/"`.
  2. Run `timeout 300 python3 -m pytest tests/workflow_core/test_attach_store.py tests/workflow_core/test_attachments_settings.py -q`: fails.
  3. Code:
     - `attach_store.py`: `StoreError`, `blob_path`, the `Store` protocol as in Interfaces, and `LocalStore(directory: Path)` with `name = "local"`.
     - `attachments.py`: module docstring `"""gin attach: images on beads, kept in a shared store and listed in metadata.attachments."""`, `SCHEME`, `DEFAULT_MAX_BYTES`, `AttachmentError(message, code=2)`, `Settings`, and:
       ```python
       def load_settings(repo: Path) -> Settings:
           try:
               config = resolve_effective_config(main_checkout(Path(repo).resolve()), write=False).config.to_dict()
           except ConfigValidationError as error:
               raise AttachmentError(f"invalid configuration: {error}") from error
           section = config.get("attachments") or {}
           settings = Settings(store=section.get("store", "git-ref"),
                               max_bytes=int(section.get("max_bytes", DEFAULT_MAX_BYTES)),
                               retention_days=section.get("retention_days"), s3=dict(section.get("s3") or {}))
           if settings.store == "s3" and not settings.s3.get("bucket"):
               raise AttachmentError("attachments.store is s3 but attachments.s3.bucket is not set")
           return settings


       def open_store(repo: Path, settings: Settings) -> Store:
           main = main_checkout(Path(repo).resolve())
           if settings.store == "local":
               return LocalStore(main / ".agent-workflow/attachments")
           if settings.store == "s3":
               from .attach_s3 import S3Store
               return S3Store(**settings.s3)
           from .attach_gitref import GitRefStore
           return GitRefStore(main)
       ```
     - `schemas.py`, after the `usage` entry:
       ```python
       "attachments": {
           "type": "object",
           "properties": {
               "store": {"enum": ["git-ref", "local", "s3"]},
               "max_bytes": {"type": "integer", "minimum": 1},
               "retention_days": {"type": "integer", "minimum": 1},
               "s3": {
                   "type": "object",
                   "properties": {"bucket": {"type": "string", "minLength": 1},
                                  "prefix": {"type": "string"},
                                  "endpoint_url": {"type": "string", "minLength": 1},
                                  "region": {"type": "string", "minLength": 1}},
                   "additionalProperties": False,
               },
           },
           "additionalProperties": False,
       },
       ```
     - `setup_service.py`: add `"attachments/",` to `LOCAL_GITIGNORE_ENTRIES`.
  4. Run the two tests plus `timeout 600 python3 -m pytest tests/workflow_core/test_configuration.py tests/workflow_core/test_setup_cli.py tests/workflow_core/test_migrations.py -q`: passes.
  5. Commit: `feat(attach): store protocol, local store, and the attachments config section (gin-workflow-s6fv)`.
- **Acceptance criteria**: `Settings` reads the section with its defaults; s3 without a bucket and unknown stores are refused; `LocalStore` round-trips blobs; setup gitignores `.agent-workflow/attachments/`.
- **Estimated complexity**: medium

### Track 3: The git-ref store
- **Dependencies**: Track 2
- **Files**:
  - Create `plugins/gin-workflow/src/scripts/workflow_core/attach_gitref.py`
  - Test `tests/workflow_core/test_attach_gitref.py`
- **Provider role**: `backend`
- **Model:** `opus`
- **Effort:** `high`
- **Why:** concurrent pushes from several clones, tree-union merges, and a forced rewrite guarded by a lease.
- **Steps**:
  1. `tests/workflow_core/test_attach_gitref.py`. Fixture: a bare `origin.git` and two clones `a` and `b` made with `git init` plus `git remote add origin <bare>` (no commit needed). Helper `sha(data) = hashlib.sha256(data).hexdigest()`. Tests:
     - `put` in `a` returns `blob_path(sha)`, creates `refs/gin/attachments` with that path in its tree, needs no network, and `get` returns the bytes; `put` of the same sha adds no commit.
     - `push()` from `a` returns `None`; `git ls-remote <bare> refs/gin/attachments` shows the local tip.
     - Race: `a` and `b` each `put` a different blob, `a.push()`, then `b.push()` returns `None`; after `a.fetch()`, `a.paths()` holds both paths and `git -C <bare> ls-tree -r --name-only refs/gin/attachments` lists both.
     - `fetch()` in `b` after `a` pushed brings the blob; `b.get(path)` returns it.
     - Push rejected three times (patch `GitRefStore._push_once` to return a non-zero `CompletedProcess`): `push()` returns a warning that names `gin attach push`, and the local ref keeps the blob.
     - No `origin` remote: `put` works, `push()` returns a warning that the files stay on this machine, `fetch()` does nothing.
     - `remove([path])` after both pushed: the local ref is one parentless commit without that path, `origin` matches, and the other path stays.
     - Lost lease: after `a.fetch()`, `b` pushes a new blob; `a.remove([...])` raises `StoreError` naming `gin attach prune --apply`, and `origin` still holds `b`'s blob.
     - `get` of a path that is not in the tree raises `StoreError`.
  2. Run `timeout 600 python3 -m pytest tests/workflow_core/test_attach_gitref.py -q`: fails.
  3. Create `attach_gitref.py`:
     ```python
     """The git-ref attachment store: one commit history on refs/gin/attachments, blobs at <aa>/<sha256>."""

     from __future__ import annotations

     import os
     from pathlib import Path
     import subprocess
     import tempfile
     from typing import Collection, Mapping

     from .attach_store import StoreError, blob_path

     REF = "refs/gin/attachments"
     REMOTE_REF = "refs/gin/attachments-origin"
     ZERO = "0" * 40
     ATTEMPTS = 3


     class GitRefStore:
         name = "git-ref"

         def __init__(self, repo: Path, remote: str = "origin") -> None:
             self.repo, self.remote = Path(repo), remote

         def _git(self, *args: str, data: bytes | None = None, env: Mapping[str, str] | None = None,
                  check: bool = True) -> subprocess.CompletedProcess[bytes]:
             done = subprocess.run(["git", *args], cwd=self.repo, input=data, capture_output=True, check=False,
                                   env={**os.environ, "GIT_TERMINAL_PROMPT": "0", **(env or {})})
             if check and done.returncode != 0:
                 raise StoreError(f"git {args[0]} failed: {done.stderr.decode(errors='replace').strip()}")
             return done

         def _out(self, *args: str, **kwargs) -> str:
             return self._git(*args, **kwargs).stdout.decode().strip()

         def _tip(self, ref: str) -> str | None:
             done = self._git("rev-parse", "-q", "--verify", f"{ref}^{{commit}}", check=False)
             return done.stdout.decode().strip() or None

         def _has_remote(self) -> bool:
             return self._git("remote", "get-url", self.remote, check=False).returncode == 0

         def _identity(self) -> dict[str, str]:
             email = self._git("config", "user.email", check=False).stdout.decode().strip() or "gin@localhost"
             return {"GIT_AUTHOR_NAME": "gin attach", "GIT_AUTHOR_EMAIL": email,
                     "GIT_COMMITTER_NAME": "gin attach", "GIT_COMMITTER_EMAIL": email}

         def _listing(self, commit: str | None) -> dict[str, str]:
             """{path: blob id} of a commit's tree."""
             if commit is None:
                 return {}
             rows = self._out("ls-tree", "-r", commit).splitlines()
             return {line.split("\t", 1)[1]: line.split()[2] for line in rows if "\t" in line}

         def _commit(self, blobs: Mapping[str, str], parents: list[str], message: str) -> str:
             handle, index = tempfile.mkstemp(prefix="gin-attach-index-")
             os.close(handle)
             os.unlink(index)
             env = {"GIT_INDEX_FILE": index}
             try:
                 self._git("read-tree", "--empty", env=env)
                 for path, blob in sorted(blobs.items()):
                     self._git("update-index", "--add", "--cacheinfo", f"100644,{blob},{path}", env=env)
                 tree = self._out("write-tree", env=env)
             finally:
                 if os.path.exists(index):
                     os.unlink(index)
             parent_args = [arg for parent in parents for arg in ("-p", parent)]
             return self._out("commit-tree", tree, *parent_args, data=message.encode(), env=self._identity())

         def _set(self, commit: str, old: str | None) -> None:
             self._git("update-ref", REF, commit, old or ZERO)

         def _fetch_remote(self) -> str | None:
             if not self._has_remote():
                 return None
             listed = self._git("ls-remote", self.remote, REF, check=False)
             if listed.returncode != 0:
                 raise StoreError(f"cannot reach {self.remote}: {listed.stderr.decode(errors='replace').strip()}")
             if not listed.stdout.strip():
                 return None
             self._git("fetch", "--quiet", self.remote, f"+{REF}:{REMOTE_REF}")
             return self._tip(REMOTE_REF)

         def _merge(self, local: str | None, remote: str | None) -> str | None:
             """The local tip after taking in the remote one; content-addressed paths never conflict."""
             if remote is None or remote == local:
                 return local
             if local is None or self._git("merge-base", "--is-ancestor", local, remote, check=False).returncode == 0:
                 return remote
             if self._git("merge-base", "--is-ancestor", remote, local, check=False).returncode == 0:
                 return local
             blobs = {**self._listing(remote), **self._listing(local)}
             return self._commit(blobs, [remote, local], "merge attachments")

         def fetch(self) -> None:
             local, remote = self._tip(REF), self._fetch_remote()
             merged = self._merge(local, remote)
             if merged != local:
                 self._set(merged, local)

         def put(self, sha256: str, data: bytes) -> str:
             path, local = blob_path(sha256), self._tip(REF)
             listing = self._listing(local)
             if path in listing:
                 return path
             blob = self._out("hash-object", "-w", "--stdin", data=data)
             self._set(self._commit({**listing, path: blob}, [local] if local else [], f"attach {sha256}"), local)
             return path

         def get(self, path: str) -> bytes:
             done = self._git("cat-file", "blob", f"{REF}:{path}", check=False)
             if done.returncode != 0:
                 raise StoreError(f"{path}: not in {REF}; run gin attach fetch")
             return done.stdout

         def paths(self) -> set[str]:
             return set(self._listing(self._tip(REF)))

         def _push_once(self) -> subprocess.CompletedProcess[bytes]:
             return self._git("push", "--quiet", self.remote, f"{REF}:{REF}", check=False)

         def push(self) -> str | None:
             if not self._has_remote():
                 return f"no {self.remote} remote: attachments stay on this machine"
             failure = ""
             for _ in range(ATTEMPTS):
                 self.fetch()
                 local = self._tip(REF)
                 if local is None or local == self._tip(REMOTE_REF):
                     return None
                 done = self._push_once()
                 if done.returncode == 0:
                     self._git("update-ref", REMOTE_REF, local)
                     return None
                 failure = done.stderr.decode(errors="replace").strip()
             return f"push of {REF} failed ({failure}); run gin attach push"

         def remove(self, paths: Collection[str]) -> None:
             self.fetch()
             local = self._tip(REF)
             listing = self._listing(local)
             keep = {path: blob for path, blob in listing.items() if path not in set(paths)}
             if local is None or keep == listing:
                 return
             commit = self._commit(keep, [], "prune attachments")
             self._set(commit, local)
             if not self._has_remote():
                 return
             seen = self._tip(REMOTE_REF) or ""
             # no "+" on the refspec: the lease alone allows the rewrite, and only while origin is at `seen`
             done = self._git("push", "--quiet", f"--force-with-lease={REF}:{seen}", self.remote,
                              f"{REF}:{REF}", check=False)
             if done.returncode != 0:
                 raise StoreError(f"{self.remote} changed during prune; run gin attach prune --apply again")
             self._git("update-ref", REMOTE_REF, commit)
     ```
  4. Run the test: passes. Then `timeout 600 python3 -m pytest tests/workflow_core/test_attach_store.py tests/workflow_core/test_attachments_settings.py -q`: passes.
  5. Commit: `feat(attach): git-ref store on refs/gin/attachments with merge and retry (gin-workflow-s6fv)`.
- **Acceptance criteria**: blobs round-trip; two clones pushing at once both land; a rejected push leaves the blob local with a warning; prune rewrites under a lease and refuses when `origin` moved; no remote keeps everything local.
- **Estimated complexity**: high

### Track 4: The s3 store
- **Dependencies**: Track 3
- **Files**:
  - Create `plugins/gin-workflow/src/scripts/workflow_core/attach_s3.py`
  - Test `tests/workflow_core/test_attach_s3.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** a thin wrapper over the boto3 S3 client with a stub in tests; no network.
- **Steps**:
  1. `tests/workflow_core/test_attach_s3.py` with a `StubClient` (dict-backed `head_object`, `put_object`, `get_object`, `get_paginator("list_objects_v2")`, `delete_objects`; a missing key raises an exception whose `response == {"Error": {"Code": "404"}}`). Tests:
     - `S3Store("b", prefix="team/x", client=stub)`: `put` stores key `team/x/<aa>/<sha>` and returns `<aa>/<sha>`; no call passes `ACL`; a second `put` calls only `head_object`.
     - `get` returns the bytes; a missing key raises `StoreError`.
     - `paths()` strips the prefix; with `prefix=""` keys are the paths.
     - `remove` sends one `delete_objects` per 1,000 keys with `Quiet: True`.
     - `push()` returns `None`; `fetch()` returns `None`; `name == "s3"`.
     - `require_boto3()` with `sys.modules["boto3"] = None` raises `DependencyUnavailableError` whose message holds `python3 -m pip install boto3`.
     - `S3Store("b", endpoint_url="http://minio:9000", region="us-east-1")` without a client calls `require_boto3().client("s3", endpoint_url=..., region_name=...)` (patch `attach_s3.require_boto3`).
  2. Run `timeout 300 python3 -m pytest tests/workflow_core/test_attach_s3.py -q`: fails.
  3. Create `attach_s3.py`: `require_boto3()` shaped like `configuration.require_yaml()` (`configuration.py:85-93`), raising `DependencyUnavailableError("The 'boto3' package is required for attachments.store: s3. Install it with: python3 -m pip install boto3")`; `S3Store` with `name = "s3"`, `_key(path)` (`f"{prefix.strip('/')}/{path}"` when a prefix is set), `put` (skip when `head_object` succeeds; treat an error whose `response["Error"]["Code"]` is `404`, `NoSuchKey`, or `NotFound` as missing; any other error becomes `StoreError`), `get`, `paths`, `remove` in batches of 1,000, `push` and `fetch` returning `None`. No `ACL`, no `generate_presigned_url`.
  4. Run the test: passes.
  5. Commit: `feat(attach): s3 store with boto3 as an optional dependency (gin-workflow-s6fv)`.
- **Acceptance criteria**: blobs land at `<prefix>/<aa>/<sha256>` without an ACL; a missing boto3 names the pip command; the test runs without network or boto3.
- **Estimated complexity**: medium

### Track 5: gin attach add, list, fetch, push
- **Dependencies**: Track 4
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/attachments.py` (bead I/O, `entries`, `reference`, `add`, `list_entries`, `fetch`, `push`)
  - Create `plugins/gin-workflow/src/scripts/workflow_core/attach_cli.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/cli.py:13-15` (`TOP_COMMANDS` gains `"attach"`), the dispatch chain (an `attach` branch like `milestone`)
  - Test `tests/workflow_core/test_attachments.py`
  - Test `tests/workflow_core/test_attach_cli.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded domain logic and an argparse CLI over the stores and `bd`, following `milestone_cli.py` and `scoped_commit.py`.
- **Steps**:
  1. Tests. `test_attachments.py` uses a real `bd` (skip guard) in a temporary git repository with `init_beads` from `team_fixtures.py`, a `LocalStore` passed as `store=`, and fixed `now`:
     - `add(repo, bead, [png])` returns one entry with `sha256` of the cleaned bytes, `mime` `image/png`, `bytes`, `name` the file name, `caption` `None`, `added_by` the git `user.email`, `added_at` `now` in ISO 8601 with `Z`, `store` `local`, `path` `blob_path(sha)`; `bd show --json` holds the same list under `metadata.attachments`.
     - A second `add` of the same file returns the existing entry and leaves one entry.
     - A PDF named `x.png` and a file over `max_bytes` (patch `load_settings` to `Settings(store="local", max_bytes=10)`) land in `refused` with reasons; a valid file in the same call is still added.
     - `--case`/`--step` values reach the entry; `reference(entry)` is `![<caption>](attachment:<sha>)`, or uses `name` without a caption.
     - `entries` reads a JSON string and a list alike, and returns `[]` for anything else.
     - A missing bead raises `AttachmentError` with code 2; with `providers.task_tracking: markdown` `add` raises `AttachmentError` naming Beads.
     - `fetch(repo, bead=..., out=dir)` writes `<sha>.png` with the stored bytes; a blob whose bytes do not match its sha raises `AttachmentError`.
     - `add` with a store whose `push()` returns a warning keeps the entry and returns the warning.
     `test_attach_cli.py` patches `attachments.add`, `list_entries`, `fetch`, `push` and checks: `gin attach add b f.png --caption C` prints the reference and exits 0; with a refused file it prints `refused f.pdf: <reason>` to stderr and exits 1; `--format json` prints `{"bead", "entries", "refused", "warning"}`; `list --format json` prints `{"bead", "entries"}`; `fetch --bead b` without `--out` exits 2; `push` with a warning prints it and exits 2; `AttachmentError` and `DependencyUnavailableError` exit 2 with `error: <message>`; `cli.main(["attach", "list", "x"])` reaches `attach_cli.main`.
  2. Run `timeout 600 python3 -m pytest tests/workflow_core/test_attachments.py tests/workflow_core/test_attach_cli.py -q`: fails.
  3. Code in `attachments.py`:
     - `_bd(repo, argv)` like `specs._bd` (`specs.py:1050-1068`), except that the markdown backend raises `AttachmentError("gin attach needs Beads (providers.task_tracking: beads)")`, and a non-zero exit raises `AttachmentError` with bd's stderr.
     - `_show(repo, bead)`: `bd show <bead> --json`, first element when a list; no record raises `AttachmentError(f"{bead}: no such bead")`.
     - `entries(row)`: `metadata.attachments` parsed from a JSON string or taken as a list of mappings.
     - `add`: for each file read the bytes (`OSError` refused as `cannot read`), `sniff` (None refused as `not a PNG, JPEG, WebP or GIF`), `clean` (`ValueError` refused as `malformed <type>: <error>`), size check against `settings.max_bytes`, sha256; an sha the bead holds in an entry without `pruned_at` returns the existing entry; else `store.put` then build the entry (a pruned entry stays, and the new entry is appended). When there are new entries, write `bd update <bead> --set-metadata attachments=<json.dumps(old + new, sort_keys=True)>`, then `warning = store.push()`. `added_by` comes from `team.git_email(main)`.
     - `list_entries`, `fetch` (always `store.fetch()`; with `bead` and `out`, write each entry without `pruned_at` to `out/<sha>.<EXTENSIONS[mime]>` after checking the sha256), `push` (`store.push()`).
     - `attach_cli.main`: subcommands `add <bead> <file>... [--caption] [--case] [--step N] [--format]`, `list <bead> [--format]`, `fetch [--bead --out]`, `push`, each with `--repository` defaulting to `workspace.repository_root(None)` as `milestone_cli` does; exit codes per the Global Constraints.
     - `cli.py`: add `"attach"` to `TOP_COMMANDS` and the branch `if argv[0] == "attach": from .attach_cli import main as attach_main; return attach_main(argv[1:])`.
  4. Run the two tests, then `timeout 900 python3 -m pytest -n auto -q`: passes.
  5. Commit: `feat(attach): gin attach add, list, fetch and push (gin-workflow-s6fv)`.
- **Acceptance criteria**: US-1, US-2 (`fetch --out`), US-3 (`list --format json`), US-4 (store choice), and US-7 (`push` after a failed push) hold through the CLI; every entry's sha256 is a blob in the store; the full suite passes.
- **Estimated complexity**: medium

### Track 6: gin attach prune
- **Dependencies**: Track 5
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/attachments.py` (`prune`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/attach_cli.py` (`prune [--apply] [--format]`)
  - Test `tests/workflow_core/test_attachments_prune.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** a selection rule over bead rows and store paths, then one removal and metadata update per bead.
- **Steps**:
  1. `test_attachments_prune.py` (real `bd`, skip guard, `LocalStore`, fixed `now`): an orphan blob (`store.put` with no entry) is listed with reason `orphan`; with `retention_days: 30`, a blob whose only bead closed 40 days ago is listed with reason `closed <date>`, one whose bead closed 10 days ago is not, and one shared by an open bead and an old closed bead is not; without `retention_days` only orphans are listed; the dry run changes nothing; `apply=True` removes exactly the listed paths and sets `pruned_at` on their entries; entries already holding `pruned_at` do not count as references; CLI `prune` text lists `<path> <reason>`, `--format json` prints `{"candidates": [...], "applied": bool}`.
     To close a bead in the past, set `closed_at` through the row the test passes: build rows from `bd list --all -n 0 --json` and patch `attachments._rows` to return them with `closed_at` rewritten.
  2. Run `timeout 600 python3 -m pytest tests/workflow_core/test_attachments_prune.py -q`: fails.
  3. Code: `_rows(repo)` runs `bd list --all -n 0 --json`. `prune`: `store.fetch()`, then map each store path to the rows whose live entries (no `pruned_at`) reference it; candidates are paths with no live reference (`orphan`), and, with `retention_days`, paths whose referencing rows are all `closed` with the newest `closed_at` before `now - retention_days` (`closed <YYYY-MM-DD>`). With `apply`, `store.remove(candidate paths)`, then per touched bead set `pruned_at` on matching entries and write `attachments` back. Return `{"candidates": [{"path", "sha256", "reason", "beads"}], "applied": apply}`. The text output of a dry run that lists an orphan ends with `run bd dolt pull first: a blob whose entry has not reached this machine counts as an orphan`.
  4. Run the test: passes.
  5. Commit: `feat(attach): gin attach prune for orphans and long-closed beads (gin-workflow-s6fv)`.
- **Acceptance criteria**: US-5 holds; a dry run changes neither store nor beads.
- **Estimated complexity**: medium

### Track 7: gin-qa cases bug attaches its screenshots
- **Dependencies**: Track 6
- **Files**:
  - Modify `plugins/gin-qa/src/scripts/gin_qa/bugs.py:82-160` (`description`, `rerun_note`, `file_bug`, new `_images`, `_attach`)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/cli.py:241-245` (print `warnings` to stderr)
  - Test `tests/gin_qa/test_cases_bug.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** one caller change in gin-qa over the `gin attach` CLI; the stub `gin` in `test_cases_bug.py` already logs every call.
- **Steps**:
  1. Tests in `test_cases_bug.py`, using its stub `gin` with an answer for `attach add` that prints `{"bead": "...", "entries": [{"sha256": "<64 hex>", "path": "...", ...}], "refused": [], "warning": null}`:
     - A case whose `Run` is an e2e run folder (`run.json`, `<tc lowercase>/result.json` with step 2 `failed`, `screenshot` `02.png`, and `02.png` on disk): the new bug's description, rewritten by `gin task update <bug> --body-file -`, holds `- ![TC-AUTH-001 step 2: <title>](attachment:<sha>)` followed by `  local: <relative path of 02.png>`; the `attach add` call carries `--case TC-AUTH-001 --step 2 --format json`.
     - `--evidence shot.png` (an existing file) becomes an attachment line; `--evidence "see log"` stays `- see log`.
     - The case's open bug path: `attach add` runs on the open bug before the note, and the note's `Evidence:` lists `attachment:<sha>`.
     - `attach add` exiting 2: the bug is still created with the plain local lines, `warnings` holds the stderr, and the CLI prints `warning: ...`.
     - No image at all: no `attach add` call and no `--body-file` update.
  2. Run `timeout 600 python3 -m pytest tests/gin_qa/test_cases_bug.py -q`: fails.
  3. Code in `bugs.py`:
     - `_images(root, eff, case, run, evidence) -> list[tuple[Path, str, int | None, str]]` returns `(file, label, step, local)`: each `evidence` value whose `root / value` (or absolute path) is a file with suffix `.png`, `.jpg`, `.jpeg`, `.webp`, or `.gif` (label `TC: <name>`), then, when `run` names a folder under `evidence_root(eff)` with `run.json` (`e2e._run_folder`), every `failed` step of each `e2e._result_folders(<run>/<tc lowercase>)` `result.json` (`e2e._result`) whose `screenshot` file exists (label `<tc> step <n>: <title>`).
     - `_attach(project, bug, images) -> tuple[dict[str, str], list[str]]` calls `gin attach add <bug> <file> --case <tc> [--step <n>] --caption <label> --format json` per image and returns `{local path: sha256}` and warnings (stderr or refused reasons).
     - `description(...)` takes an optional `attached: Mapping[str, tuple[str, str]]` (local path to `(label, sha)`) and writes `- ![<label>](attachment:<sha>)` plus `  local: <path>` for those, the other evidence values as before; `rerun_note` lists `attachment:<sha>` values after `Evidence:`.
     - `file_bug`: on the open-bug path, attach first, then append the note; on the new-bug path, create the bug as today, record the result, then attach and, when any image was attached, `gin task update <bug> --body-file -` with the new description on stdin. A failed update or attach adds a warning; it never raises. The returned dict gains `attachments` (list of sha256) and `warnings`.
     - `cli.py`: print each warning as `warning: <text>` to stderr after the result.
  4. Run the test, then `timeout 900 python3 -m pytest -n auto -q`: passes.
  5. Commit: `feat(gin-qa): cases bug attaches image evidence and failed e2e step screenshots (gin-workflow-s6fv)`.
- **Acceptance criteria**: US-6 holds; filing a bug never fails because of an attachment.
- **Estimated complexity**: medium

### Track 8: Docs
- **Dependencies**: Track 7
- **Files**:
  - Modify `docs/reference/cli.md` (new `## gin attach` section after `## gin milestone`; the top-level command list)
  - Modify `docs/reference/config.md` (new `### attachments` section after `### qa`)
  - Modify `docs/guides/qa.md`, `docs/guides/qa.vi.md` (bug evidence becomes attachments)
  - Modify `docs/concepts/state-model.md` (where attachments live)
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `low`
- **Why:** reference text from the code of Tracks 1 to 7; no design judgement.
- **Steps**:
  1. `cli.md` `## gin attach`: the five subcommands with their options and output; exit codes; the stores; the reader contract: a read-only reader that never runs `gin attach add` fetches `+refs/gin/attachments:refs/gin/attachments`, any other clone runs `gin attach fetch` (the forced fetch drops unpushed blobs); blob at `<aa>/<sha256>` read with `git cat-file blob refs/gin/attachments:<path>`; the `metadata.attachments` entry fields; the `attachment:<sha256>` Markdown reference. Also say: the `git-ref` store needs git 2.29 or later; its pushes run the repository's pre-push hooks (gin does not pass `--no-verify`); run `bd dolt pull` before `gin attach prune --apply`, because a blob whose entry has not reached this machine yet counts as an orphan.
  2. `config.md` `### attachments`: `store`, `max_bytes`, `retention_days`, `s3.{bucket,prefix,endpoint_url,region}`, credentials from boto3's default chain, `pip install boto3` for `s3`, and "needs gin-workflow 3.5.0 or later; older versions ignore the section and attach nothing".
  3. `qa.md` and `qa.vi.md`: where `cases bug` evidence is explained (around `:107`), say that image evidence and failed e2e step screenshots are attached and referenced, and keep the local path.
  4. `state-model.md`: one row for "Where do bead images live?" naming `refs/gin/attachments` (or the configured store) and `metadata.attachments`.
  5. Run `gin docs check` on the changed pages: `ok`. Run `timeout 300 python3 -m pytest tests/workflow_core/test_rename_sweep.py tests/workflow_core/test_retired_usage_sweep.py -q`: passes.
  6. Commit: `docs: gin attach, the attachments config section, and gin-qa attachments (gin-workflow-s6fv)`.
- **Acceptance criteria**: every command, flag, default, and path in the docs matches the code; `gin docs check` prints `ok`.
- **Estimated complexity**: low

## Integration
- **Branch**: `feat/bead-attachments`
- **Merge strategy**: sequential
- After the merge into `master`: push once, then `./install.sh` once the push has finished; `bd ship bead-attachments` so `gin-console-rm-shared-attachments` can start.

## Validation
- [ ] `timeout 900 python3 -m pytest -n auto -q` passes on `feat/bead-attachments` after Track 8
- [ ] `gin docs check` prints `ok` for the changed pages
- [ ] Manual: in two clones of a scratch repository with a bare origin, `gin attach add` in one and `gin attach fetch --bead <id> --out out/` in the other after `bd dolt pull` give the same bytes
- [ ] The Windows job of `.github/workflows/test.yml` passes before the release tag

## Notes
- The user may override `Model:` and `Effort:` before plan approval.
- Provider roles describe responsibility rather than filename patterns.
- The Parent Bead stays open until the human-confirmed merge; track beads close when their tests and review pass.
- Line numbers are from `master` at `65c5631f`; a later track sees them shifted by earlier ones and locates code by the quoted names.
