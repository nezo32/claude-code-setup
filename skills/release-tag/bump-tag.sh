#!/usr/bin/env bash
# bump-tag.sh - compute the next semver tag from the latest one and push it,
# which triggers that repo's tag pipeline.
#
# Single repo:
#   bump-tag.sh [module] [patch|minor|major]   # default: current repo, patch
#   bump-tag.sh minor                          # current repo, minor
#   bump-tag.sh service-a major                # submodule "service-a", major
#
# All modules with unreleased changes:
#   bump-tag.sh --all [patch|minor|major]
#
# Env:
#   DRY_RUN=1          print what it would do, push nothing
#   RELEASE_MODULES    space-separated module dirs for --all (default: .gitmodules)
#   RELEASE_BRANCH     branch a release must sit on (default: main)
set -uo pipefail

BRANCH="${RELEASE_BRANCH:-main}"

ALL=0
if [ "${1:-}" = "--all" ] || [ "${1:-}" = "full" ]; then
  ALL=1; LEVEL="${2:-patch}"
elif [[ "${1:-}" =~ ^(patch|minor|major)$ ]]; then
  MODULE="."; LEVEL="$1"
else
  MODULE="${1:-.}"; LEVEL="${2:-patch}"
fi
[[ "$LEVEL" =~ ^(patch|minor|major)$ ]] || { echo "level must be patch|minor|major, got '$LEVEL'"; exit 1; }

# Release one repo dir. Exit codes: 0 tagged, 1 skipped, 2 error.
# Every failure is checked explicitly: `set -e` is ignored inside a function that
# is called as part of an `&&` / `||` list, which is how it is called below.
release_one() (
  dir="$1"; level="$2"
  cd "$dir" 2>/dev/null || { echo "x ${dir}: no such directory"; exit 2; }
  repo="$(basename "$(git rev-parse --show-toplevel)")" || { echo "x ${dir}: not a git repo"; exit 2; }

  branch="$(git rev-parse --abbrev-ref HEAD)"
  [ "$branch" = "$BRANCH" ]          || { echo ". ${repo}: skip - on '${branch}', not ${BRANCH}"; exit 1; }
  [ -z "$(git status --porcelain)" ] || { echo ". ${repo}: skip - working tree is dirty"; exit 1; }

  git fetch --quiet --tags origin || { echo "x ${repo}: git fetch origin failed"; exit 2; }
  if git rev-parse --verify --quiet "origin/$BRANCH" >/dev/null; then
    [ "$(git rev-parse HEAD)" = "$(git rev-parse "origin/$BRANCH")" ] \
      || { echo ". ${repo}: skip - ${BRANCH} is not level with origin/${BRANCH}"; exit 1; }
  fi

  latest="$(git tag --list --sort=-v:refname | grep -E '^v?[0-9]+\.[0-9]+\.[0-9]+$' | head -n1 || true)"
  if [ -z "$latest" ]; then
    new="v0.1.0"
  else
    [ "$(git rev-list "${latest}..HEAD" --count)" -gt 0 ] \
      || { echo ". ${repo}: skip - no commits since ${latest}"; exit 1; }
    prefix=""; ver="$latest"
    [ "${latest#v}" != "$latest" ] && { prefix="v"; ver="${latest#v}"; }
    IFS=. read -r MA MI PA <<< "$ver"
    case "$level" in
      major) MA=$((MA + 1)); MI=0; PA=0 ;;
      minor) MI=$((MI + 1)); PA=0 ;;
      patch) PA=$((PA + 1)) ;;
    esac
    new="${prefix}${MA}.${MI}.${PA}"
  fi

  if git rev-parse --verify --quiet "refs/tags/$new" >/dev/null; then
    echo "x ${repo}: tag ${new} already exists"; exit 2
  fi

  if [ "${DRY_RUN:-}" = "1" ]; then
    echo "  ${repo}: ${latest:-<none>} -> ${new}  (dry-run)"; exit 0
  fi

  git tag -a "$new" -m "release $new" || { echo "x ${repo}: git tag failed"; exit 2; }
  git push --quiet origin "$new" || { echo "x ${repo}: push of ${new} failed (local tag kept)"; exit 2; }
  echo "ok ${repo}: pushed ${new}"
)

if [ "$ALL" = 1 ]; then
  root="$(git rev-parse --show-toplevel)"
  if [ -n "${RELEASE_MODULES:-}" ]; then
    modules="$RELEASE_MODULES"
  else
    modules="$(cd "$root" && git config --file .gitmodules --get-regexp '\.path$' 2>/dev/null | awk '{print $2}' | tr '\n' ' ')"
  fi
  [ -n "$modules" ] || { echo "no modules: set RELEASE_MODULES or add submodules"; exit 2; }
  echo "release-tag --all (${LEVEL})${DRY_RUN:+ [dry-run]}: modules with commits since their last tag:"
  tagged=0; skipped=0; errors=0
  for m in $modules; do
    release_one "$root/$m" "$LEVEL" && rc=0 || rc=$?
    case "$rc" in 0) tagged=$((tagged + 1)) ;; 1) skipped=$((skipped + 1)) ;; *) errors=$((errors + 1)) ;; esac
  done
  echo "done: ${tagged} tagged, ${skipped} skipped, ${errors} error(s)"
  [ "$errors" -eq 0 ]
  exit $?
fi

dir="."
[ "$MODULE" != "." ] && dir="$(git rev-parse --show-toplevel)/$MODULE"
release_one "$dir" "$LEVEL" && rc=0 || rc=$?
[ "$rc" -eq 1 ] && exit 1   # skipped (e.g. no changes) is not success
exit "$rc"
