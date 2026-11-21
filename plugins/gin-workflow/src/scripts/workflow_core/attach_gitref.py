"""The git-ref attachment store: one commit history on refs/gin/attachments, blobs at <aa>/<sha256>."""

from __future__ import annotations

from collections.abc import Collection, Mapping
import os
from pathlib import Path
import subprocess
import tempfile

from .attach_store import StoreError, blob_path, check_path

REF = "refs/gin/attachments"
REMOTE_REF = "refs/gin/attachments-origin"
PRUNE = "prune attachments"  # the subject of the parentless commit a prune writes
ATTEMPTS = 3


def _stderr(done: subprocess.CompletedProcess[bytes]) -> str:
    return done.stderr.decode(errors="replace").strip()


def _is_store_path(path: str) -> bool:
    try:
        check_path(path)
    except StoreError:
        return False
    return True


class GitRefStore:
    name = "git-ref"

    def __init__(self, repo: Path, remote: str = "origin") -> None:
        self.repo, self.remote = Path(repo), remote

    def _git(self, *args: str, data: bytes | None = None, env: Mapping[str, str] | None = None,
             check: bool = True) -> subprocess.CompletedProcess[bytes]:
        try:
            done = subprocess.run(["git", *args], cwd=self.repo, input=data, capture_output=True, check=False,
                                  env={**os.environ, "GIT_TERMINAL_PROMPT": "0", **(env or {})})
        except OSError as error:
            raise StoreError(f"cannot run git: {error}") from error
        if check and done.returncode != 0:
            raise StoreError(f"git {args[0]} failed: {_stderr(done)}")
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
        """{path: blob id} of the <aa>/<sha256> blobs in a commit's tree; any other entry is left out."""
        if commit is None:
            return {}
        listing = {}
        for row in self._git("ls-tree", "-r", "-z", commit).stdout.decode(errors="replace").split("\0"):
            meta, _, path = row.partition("\t")
            fields = meta.split()
            if len(fields) == 3 and fields[1] == "blob" and _is_store_path(path):
                listing[path] = fields[2]
        return listing

    def _commit(self, blobs: Mapping[str, str], parents: list[str], message: str) -> str:
        rows = "".join(f"100644 {blob}\t{path}\n" for path, blob in sorted(blobs.items()))
        with tempfile.TemporaryDirectory(prefix="gin-attach-") as directory:
            env = {"GIT_INDEX_FILE": str(Path(directory) / "index")}
            self._git("update-index", "--index-info", data=rows.encode(), env=env)
            tree = self._out("write-tree", env=env)
        parent_args = [arg for parent in parents for arg in ("-p", parent)]
        return self._out("commit-tree", tree, *parent_args, data=message.encode(), env=self._identity())

    def _set(self, commit: str, old: str | None) -> None:
        """Move REF to commit only while it is still at old (an empty old value: only while it does not exist)."""
        self._git("update-ref", REF, commit, old or "")

    def _fetch_remote(self) -> str | None:
        """The remote's tip, fetched into REMOTE_REF; None when the remote has no attachments ref."""
        if not self._has_remote():
            return None
        listed = self._git("ls-remote", self.remote, REF, check=False)
        if listed.returncode != 0:
            raise StoreError(f"cannot reach {self.remote}: {_stderr(listed)}")
        if not any(line.split("\t")[-1] == REF for line in listed.stdout.decode().splitlines()):
            self._git("update-ref", "-d", REMOTE_REF)
            return None
        fetched = self._git("fetch", "--quiet", "--no-write-fetch-head", self.remote, f"+{REF}:{REMOTE_REF}",
                            check=False)
        if fetched.returncode != 0:
            raise StoreError(f"git fetch failed: {_stderr(fetched)} (gin attach needs git 2.29 or later)")
        return self._tip(REMOTE_REF)

    def _merge(self, local: str | None, remote: str | None, seen: str | None) -> str | None:
        """The local tip after taking in the remote one: the remote's blobs plus those only this clone has,
        less those a prune on the remote dropped. The result has the remote tip as its only parent,
        which keeps pruned history off the remote."""
        if remote is None or remote == local:
            return local
        if local is None or self._git("merge-base", "--is-ancestor", local, remote, check=False).returncode == 0:
            return remote
        if self._git("merge-base", "--is-ancestor", remote, local, check=False).returncode == 0:
            return local
        theirs, pruned = self._listing(remote), self._pruned(local, remote, seen)
        added = {path: blob for path, blob in self._listing(local).items() if path not in theirs and path not in pruned}
        if not added:
            return remote
        return self._commit({**theirs, **added}, [remote], "merge attachments")

    def _pruned(self, local: str, remote: str, seen: str | None) -> set[str]:
        """Paths of `seen` (the remote's previous tip) that a prune on the remote dropped since, less those
        this clone attached again since `seen`; none when the remote's root is not a prune newer than `seen`
        (the ref was deleted or replaced some other way)."""
        if seen is None:
            return set()
        roots = self._out("log", "--max-parents=0", "--format=%s", remote, "--not", seen).splitlines()
        if PRUNE not in roots:
            return set()
        subjects = self._out("log", "--format=%s", f"{seen}..{local}").splitlines()
        again = {subject.removeprefix("attach ") for subject in subjects if subject.startswith("attach ")}
        return {path for path in self._listing(seen) if path.split("/")[1] not in again}

    def fetch(self) -> None:
        seen = self._tip(REMOTE_REF)
        remote = self._fetch_remote()
        local = self._tip(REF)
        try:
            merged = self._merge(local, remote, seen)
            if merged != local:
                self._set(merged, local)
        except StoreError:
            # REMOTE_REF goes back to the tip this clone took in, so the next fetch still sees what was pruned
            self._git("update-ref", *((REMOTE_REF, seen) if seen else ("-d", REMOTE_REF)))
            raise

    def put(self, sha256: str, data: bytes) -> str:
        path, local = blob_path(sha256), self._tip(REF)
        listing = self._listing(local)
        if path not in listing:
            listing = {**listing, path: self._out("hash-object", "-w", "--stdin", data=data)}
        elif path not in self._listing(self._tip(REMOTE_REF)):
            return path
        # a known path gets a commit too while the remote had it: the remote may have pruned it since (see _pruned)
        self._set(self._commit(listing, [local] if local else [], f"attach {sha256}"), local)
        return path

    def get(self, path: str) -> bytes:
        done = self._git("cat-file", "blob", f"{REF}:{check_path(path)}", check=False)
        if done.returncode != 0:
            raise StoreError(f"{path}: not in {REF}; run gin attach fetch")
        return done.stdout

    def paths(self) -> set[str]:
        return set(self._listing(self._tip(REF)))

    def push(self) -> str | None:
        if not self._has_remote():
            return f"no {self.remote} remote: attachments stay on this machine"
        failure = ""
        for _ in range(ATTEMPTS):
            try:
                self.fetch()
            except StoreError as error:
                failure = str(error)
                break
            local = self._tip(REF)
            if local is None or local == self._tip(REMOTE_REF):
                return None
            done = self._git("push", "--quiet", self.remote, f"{local}:{REF}", check=False)
            if done.returncode == 0:
                self._git("update-ref", REMOTE_REF, local)
                return None
            failure = _stderr(done)
        return f"push of {REF} to {self.remote} failed ({failure}); run gin attach push"

    def remove(self, paths: Collection[str]) -> None:
        doomed = {check_path(path) for path in paths}
        if not doomed:
            return
        self.fetch()
        local = self._tip(REF)
        listing = self._listing(local)
        keep = {path: blob for path, blob in listing.items() if path not in doomed}
        if keep == listing:
            return
        commit = self._commit(keep, [], PRUNE)
        if not self._has_remote():
            self._set(commit, local)
            return
        seen = self._tip(REMOTE_REF) or ""
        # no "+" on the refspec: the lease alone allows the rewrite, and only while the remote is at `seen`
        done = self._git("push", "--quiet", f"--force-with-lease={REF}:{seen}", self.remote, f"{commit}:{REF}",
                         check=False)
        if done.returncode != 0:
            raise StoreError(f"push of {REF} to {self.remote} failed ({_stderr(done)}); "
                             "run gin attach prune --apply again")
        try:
            self._set(commit, local)
        except StoreError:
            # another put moved the local ref after the push; REMOTE_REF still holds the old tip,
            # so a fetch takes the pruned tip in and keeps only what was attached since
            self.fetch()
            return
        self._git("update-ref", REMOTE_REF, commit)
