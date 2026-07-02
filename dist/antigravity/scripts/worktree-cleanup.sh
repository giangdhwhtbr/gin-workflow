#!/bin/bash
# worktree-cleanup.sh
# Safely removes a Git worktree.

set -euo pipefail

TRACK_ID="$1"

if [ -z "$TRACK_ID" ]; then
  echo "Usage: $0 <track-id>" >&2
  exit 1
fi

# Sanitize TRACK_ID to prevent path traversal (allow only alphanumeric, dot, underscore, dash)
if [[ ! "$TRACK_ID" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "Error: invalid track-id '$TRACK_ID'" >&2
  exit 1
fi

REPO_ROOT="$(git rev-parse --show-toplevel)"
TARGET_DIR="$REPO_ROOT/.planning/worktrees/$TRACK_ID"

# Path traversal containment check
WT_ROOT="$(realpath -m "$REPO_ROOT/.planning/worktrees")"
REAL_TARGET="$(realpath -m "$TARGET_DIR")"
if [[ "$REAL_TARGET" != "$WT_ROOT"/* ]]; then
  echo "Error: resolved path escapes worktree root" >&2
  exit 1
fi

if [ ! -d "$TARGET_DIR" ]; then
  echo "Warning: Directory $TARGET_DIR does not exist. Skipping."
  exit 0
fi

# Remove worktree
if git worktree remove "$TARGET_DIR"; then
  echo "Worktree $TARGET_DIR removed."
else
  echo "Error: Failed to remove worktree at $TARGET_DIR" >&2
  exit 1
fi
