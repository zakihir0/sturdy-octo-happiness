#!/bin/bash
set -euo pipefail

# Only run in remote (Claude Code on the web) environments
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

echo "Session start hook: checking Python availability..."
python3 --version || { echo "Python3 not found"; exit 1; }
echo "Session start hook: environment ready."
