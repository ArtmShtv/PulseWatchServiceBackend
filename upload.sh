#!/usr/bin/env bash
# Быстрая отправка изменений на GitHub: add + commit + push.
# Использование: ./upload "FIX: something"
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: ./upload \"commit message\"" >&2
  exit 1
fi

msg="$*"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Error: not a git repository" >&2
  exit 1
fi

branch="$(git branch --show-current)"

git add -A

if git diff --cached --quiet; then
  echo "Nothing to commit."
  exit 0
fi

git commit -m "$msg"

# Если у ветки ещё нет upstream, создаём его при первом push
if git rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
  git push
else
  git push -u origin "$branch"
fi

echo "Uploaded to '$branch': $msg"