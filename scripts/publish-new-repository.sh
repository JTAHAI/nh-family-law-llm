#!/usr/bin/env sh
set -eu
OWNER="${1:-JTAHAI}"
REPO="${2:-nh-family-law-llm}"
VISIBILITY="${3:-public}"
command -v gh >/dev/null 2>&1 || { echo "GitHub CLI (gh) is required" >&2; exit 1; }
gh auth status
if [ ! -d .git ]; then
  git init -b main
  git config user.name Justin
  git config user.email 43018008+JTAHAI@users.noreply.github.com
  git add -A
  git commit -m "feat: initialize New Hampshire Family Law LLM"
fi
FULL="$OWNER/$REPO"
if gh repo view "$FULL" >/dev/null 2>&1; then
  git remote get-url origin >/dev/null 2>&1 || git remote add origin "https://github.com/$FULL.git"
  git push -u origin main
else
  gh repo create "$FULL" "--$VISIBILITY" --description "Source-grounded legal AI workbench for New Hampshire family law" --source . --remote origin --push
fi
printf 'Published: https://github.com/%s\n' "$FULL"
