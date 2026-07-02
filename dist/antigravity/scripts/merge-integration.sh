#!/bin/bash
# merge-integration.sh
# Merges a completed track's branch into the integration branch.

set -euo pipefail

BRANCH_NAME="$1"
INTEGRATION_BRANCH="$2"

if [ -z "$BRANCH_NAME" ] || [ -z "$INTEGRATION_BRANCH" ]; then
  echo "Usage: $0 <track-branch-name> <integration-branch>" >&2
  exit 1
fi

# Validate both branches exist
if ! git rev-parse --verify "$BRANCH_NAME" >/dev/null 2>&1; then
  echo "Error: Branch '$BRANCH_NAME' does not exist." >&2
  exit 1
fi

if ! git rev-parse --verify "$INTEGRATION_BRANCH" >/dev/null 2>&1; then
  echo "Error: Integration branch '$INTEGRATION_BRANCH' does not exist." >&2
  exit 1
fi

# Ensure we are on the integration branch (or checkout to it)
if ! git checkout "$INTEGRATION_BRANCH"; then
  echo "Error: Cannot checkout $INTEGRATION_BRANCH (uncommitted changes?)" >&2
  exit 1
fi

# Merge the track branch
if git merge --no-ff -m "Merge branch '$BRANCH_NAME' into $INTEGRATION_BRANCH" "$BRANCH_NAME"; then
  echo "Successfully merged $BRANCH_NAME into $INTEGRATION_BRANCH"
else
  echo "Error: Conflict detected merging $BRANCH_NAME into $INTEGRATION_BRANCH" >&2
  exit 1
fi
