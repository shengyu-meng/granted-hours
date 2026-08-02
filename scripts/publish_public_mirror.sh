#!/usr/bin/env bash
set -euo pipefail

# Publish/update the sanitized Granted Hours public mirror.
# This script intentionally does NOT read private daily logs. It imports only
# public-facing free-roam artifacts declared in scripts/import_free_roam_artifacts.py,
# regenerates previews, and runs the public safety scan before any commit.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE="${GRANTED_HOURS_SOURCE:-$ROOT/../../artifacts/free-roam}"
DATE_FILTER="${1:-}"
PUBLIC_ALLOWLIST=(
  .gitattributes
  .gitignore
  ARTIST_STATEMENT.md
  LICENSE.md
  README.md
  SANITIZATION.md
  archive
  audits
  docs
  metadata
  package-lock.json
  package.json
  scripts
  src
  vite.maze.config.mjs
  vite.timetable.config.mjs
)

reject_forbidden_staged_paths() {
  local staged_path wrapped
  while IFS= read -r -d '' staged_path; do
    wrapped="/${staged_path}/"
    case "$wrapped" in
      */.private/*|*/.pytest_cache/*|*/.wrangler/*|*/node_modules/*|*/dist/*|*/raw/*|*/secrets/*|*/source/*|*/sources/*|*/logs/*)
        printf 'Refusing publication: forbidden generated/private scope is staged.\n' >&2
        return 1
        ;;
    esac
    case "$staged_path" in
      *.db|*.db-*|*.sqlite|*.sqlite3|*.log)
        printf 'Refusing publication: a database or log is staged.\n' >&2
        return 1
        ;;
    esac
  done < <(git diff --cached --name-only --diff-filter=ACMRDTUXB -z)
}

cd "$ROOT"

python3 scripts/import_free_roam_artifacts.py --source "$SOURCE"

if [[ -n "$DATE_FILTER" ]]; then
  node scripts/capture_artwork_previews.mjs --date "$DATE_FILTER"
else
  node scripts/capture_artwork_previews.mjs --all
fi

python3 scripts/check_public_safety.py
reject_forbidden_staged_paths

printf '\nGranted Hours public mirror prepared. Review changes, then stage only the public allowlist:\n' >&2
printf '  git status --short\n' >&2
printf '  git add --' >&2
printf ' %q' "${PUBLIC_ALLOWLIST[@]}" >&2
printf '\n  # Re-run this script to reject any forbidden staged paths before committing.\n' >&2

git status --short
