"""TC-ID numbering: the IDs that keep a number from a new case, and `gin-qa cases renumber`."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from . import cases as tc
from . import e2e, tests
from .reqs import Effective


def cap_of(tc_id: str) -> str | None:
    found = tc.TC_ID.fullmatch(tc_id or "")
    return found.group(1).lower() if found else None


def test_files(root: Path, eff: Effective) -> list[str]:
    """Files matched by the `Tests:` globs of the valid automated types; a declaration error drops only its type."""
    types, _ = tests.declared(root, eff)
    return tests._files(root, [glob for kind in types.values() for glob in kind.globs])


def _specs(root: Path, eff: Effective, cap: str) -> list[tuple[str, str | None, str]]:
    """(path, header TC-ID, TC-ID of the file name) of each spec in `<e2e>/<cap>/`."""
    return [(spec.path, spec.tc, PurePosixPath(spec.path).name.removesuffix(".spec.ts").upper())
            for spec in e2e.load_specs(root, eff) if spec.path.split("/")[-2] == cap]


def held(root: Path, eff: Effective, cap: str) -> set[str]:
    ids = {item for _, header, named in _specs(root, eff, cap) for item in (header, named) if item}
    ids |= {marker.tc for marker in tests.markers(root, test_files(root, eff))}
    return {item for item in ids if cap_of(item) == cap}
