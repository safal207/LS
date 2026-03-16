#!/usr/bin/env bash
set -euo pipefail

HOOK=".git/hooks/post-commit"
cp tools/git_hooks/commit_reflection.py .git/hooks/commit_reflection.py
cat > "$HOOK" <<'H'
#!/bin/sh
python3 "$(git rev-parse --show-toplevel)/tools/git_hooks/commit_reflection.py" || true
H
chmod +x .git/hooks/commit_reflection.py
chmod +x "$HOOK"
echo "post-commit hook installed"
