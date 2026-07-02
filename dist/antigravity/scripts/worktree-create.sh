#!/bin/bash
# worktree-create.sh
# Safely creates a Git worktree for isolation.

set -euo pipefail

TRACK_ID="$1"
BRANCH_NAME="$2"

if [ -z "$TRACK_ID" ] || [ -z "$BRANCH_NAME" ]; then
  echo "Usage: $0 <track-id> <branch-name> [base-ref]" >&2
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

# Make sure we don't overwrite anything by mistake
if [ -d "$TARGET_DIR" ]; then
  echo "Error: Directory $TARGET_DIR already exists." >&2
  exit 1
fi

# Derive base ref dynamically (defaulting to current branch/HEAD if unspecified)
BASE_REF="${3:-$(git symbolic-ref --short HEAD 2>/dev/null || git rev-parse --abbrev-ref HEAD || echo main)}"

# Create worktree
if git worktree add -b "$BRANCH_NAME" "$TARGET_DIR" "$BASE_REF"; then
  echo "Worktree created at: $TARGET_DIR on branch $BRANCH_NAME"
else
  echo "Error: Failed to create worktree at $TARGET_DIR" >&2
  exit 1
fi
