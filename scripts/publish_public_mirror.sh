#!/usr/bin/env bash
set -euo pipefail

# Publish/update the sanitized Granted Hours public mirror.
# This script intentionally does NOT read private daily logs. It imports only
# public-facing free-roam artifacts declared in scripts/import_free_roam_artifacts.py,
# regenerates previews, and runs the public safety scan before any commit.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE="${GRANTED_HOURS_SOURCE:-$ROOT/../../artifacts/free-roam}"
DATE_FILTER="${1:-}"

cd "$ROOT"

python3 scripts/import_free_roam_artifacts.py --source "$SOURCE"

if [[ -n "$DATE_FILTER" ]]; then
  node scripts/capture_artwork_previews.mjs --date "$DATE_FILTER"
else
  node scripts/capture_artwork_previews.mjs --all
fi

python3 scripts/check_public_safety.py

echo "\nGranted Hours public mirror prepared. Review changes, then commit/push:" >&2
echo "  git status --short" >&2
echo "  git add . && git commit -m 'Archive granted hours free-roam artifacts' && git push" >&2

git status --short
