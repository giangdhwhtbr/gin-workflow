#!/bin/bash
# remote-install.sh - Curl-pipe installer for Antigravity and other platforms.
# Usage: curl -sSL https://raw.githubusercontent.com/giangdhwhtbr/gin-workflow/master/remote-install.sh | bash -s -- [options]

set -euo pipefail

TMPDIR=$(mktemp -d -t gin-workflow-install-XXXXXX)
trap 'rm -rf "$TMPDIR"' EXIT

echo "Cloning gin-workflow repository to temporary directory..."
git clone --depth 1 https://github.com/giangdhwhtbr/gin-workflow.git "$TMPDIR/gin-workflow"

cd "$TMPDIR/gin-workflow"
echo "Running installer..."
./install.sh "$@"
echo "Installation complete!"
