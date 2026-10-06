#!/usr/bin/env bash
# Copy Action YAML into .github/workflows/ then commit+push.
# Requires a PAT with classic `workflow` scope (or equivalent fine-grained permission).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT/.github/workflows"
cp "$ROOT/scripts/github-workflows/daily-update.yml" "$ROOT/.github/workflows/"
cp "$ROOT/scripts/github-workflows/pages.yml" "$ROOT/.github/workflows/"
cd "$ROOT"
git add .github/workflows
git status
echo "Ready. Commit & push with a token that has workflow scope:"
echo "  git commit -m 'ci: install daily-update and pages workflows'"
echo "  git push"
