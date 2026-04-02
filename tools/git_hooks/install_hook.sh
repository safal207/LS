#!/usr/bin/env bash
set -euo pipefail

HOOK=".git/hooks/post-commit"
SCRIPT="tools/git_hooks/commit_reflection.py"

if [ ! -f "$SCRIPT" ]; then
  echo "Script $SCRIPT not found. Please place commit_reflection.py at tools/git_hooks/."
  exit 1
fi

cat > "$HOOK" <<'HOOK_EOF'
#!/bin/sh
python3 "$(git rev-parse --show-toplevel)/tools/git_hooks/commit_reflection.py" || true
HOOK_EOF

chmod +x "$HOOK"
echo "post-commit hook installed (will call $SCRIPT)"
