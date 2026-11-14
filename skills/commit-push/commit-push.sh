#!/usr/bin/env bash
# commit-push.sh - commit & push every git submodule, THEN the root repo.
#
# Order matters: submodules are pushed first so the root's submodule-pointer
# bumps reference commits that already exist on their remotes.
#
# Usage:
#   commit-push.sh                  # dry-run: show what each module would do
#   commit-push.sh -m "message"     # commit + push every dirty module, then the root
#   commit-push.sh -m "message" -p CLAUDE.md -p docs/foo.md
#                                   # ... and also these ROOT paths
#   commit-push.sh -m "message" --root-all
#                                   # ... and EVERYTHING in the root
#
# Per SUBMODULE:
#   detached HEAD        -> refuse (a commit there would be orphaned); skip
#   clean & up-to-date   -> skip
#   clean but ahead      -> push only (committed by hand already)
#   dirty                -> git add -A; commit -m <message>; push
#
# The ROOT, deliberately narrower:
#   stages ONLY the submodule pointers that moved, plus any `-p <path>`.
#   Everything else modified or untracked is LEFT ALONE and listed.
#   Why: a root working tree is often shared, and other sessions park
#   uncommitted work in it; `git add -A` there commits all of it under one
#   message. `--root-all` restores whole-tree staging for a checkout you own.
#
# Env:
#   COMMIT_TRAILER   attribution line(s) appended to every commit message.

set -uo pipefail

TRAILER="${COMMIT_TRAILER:-Co-Authored-By: Claude <noreply@anthropic.com>}"

MSG=""
DRYRUN=1
ROOT_ALL=0
ROOT_PATHS=()
while [ $# -gt 0 ]; do
  case "$1" in
    -m|--message) MSG="${2:-}"; DRYRUN=0; shift 2 ;;
    -p|--path) ROOT_PATHS+=("${2:-}"); shift 2 ;;
    --root-all) ROOT_ALL=1; shift ;;
    -n|--dry-run) DRYRUN=1; shift ;;
    -h|--help) sed -n '2,29p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [ "$DRYRUN" = "0" ] && [ -z "$MSG" ]; then
  echo "error: -m requires a non-empty commit message" >&2
  exit 2
fi

ROOT="$(git rev-parse --show-toplevel)" || exit 1
cd "$ROOT" || exit 1

FAIL=0

# process <path> <label> : commit (if dirty) and push one repo.
process() {
  local path="$1" label="$2" dir="$ROOT/$1"
  local branch dirty ahead=0

  branch="$(git -C "$dir" rev-parse --abbrev-ref HEAD 2>/dev/null)"
  if [ "$branch" = "HEAD" ] || [ -z "$branch" ]; then
    echo "x $label: DETACHED HEAD - checkout a branch (e.g. 'git -C $path checkout main') first; skipping"
    FAIL=1
    return
  fi

  dirty="$(git -C "$dir" status --porcelain)"
  if git -C "$dir" rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
    ahead="$(git -C "$dir" rev-list --count '@{u}..HEAD' 2>/dev/null || echo 0)"
  fi

  if [ -z "$dirty" ] && [ "$ahead" = "0" ]; then
    echo ". $label ($branch): clean, nothing to do - skip"
    return
  fi

  if [ "$DRYRUN" = "1" ]; then
    echo "> $label ($branch): WOULD act:"
    [ -n "$dirty" ] && git -C "$dir" status -s | sed 's/^/      /'
    [ "$ahead" != "0" ] && echo "      ($ahead local commit(s) to push)"
    return
  fi

  if [ -n "$dirty" ]; then
    git -C "$dir" add -A || { echo "x $label: git add failed"; FAIL=1; return; }
    printf '%s\n\n%s\n' "$MSG" "$TRAILER" | git -C "$dir" commit -q -F - \
      || { echo "x $label: commit failed"; FAIL=1; return; }
    echo "  committed $label"
  fi

  if git -C "$dir" push; then
    echo "ok $label pushed"
  else
    echo "x $label: push failed"
    FAIL=1
  fi
}

# Submodule paths in .gitmodules declaration order (auto-discovered).
SUBS=()
if [ -f .gitmodules ]; then
  mapfile -t SUBS < <(git config --file .gitmodules --get-regexp '\.path$' 2>/dev/null | awk '{print $2}')
fi

# process_root : commit the moved submodule pointers (+ any -p paths), push.
process_root() {
  local branch ahead=0 p
  local -a stage=()

  if [ "$ROOT_ALL" = "1" ]; then
    process "." "root"
    return
  fi

  branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
  if [ "$branch" = "HEAD" ] || [ -z "$branch" ]; then
    echo "x root: DETACHED HEAD - checkout a branch first; skipping"
    FAIL=1
    return
  fi
  if git rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
    ahead="$(git rev-list --count '@{u}..HEAD' 2>/dev/null || echo 0)"
  fi

  # A pointer "moved" when the submodule's checked-out commit differs from HEAD's.
  for p in "${SUBS[@]}"; do
    [ -n "$p" ] || continue
    git diff --quiet HEAD -- "$p" 2>/dev/null || stage+=("$p")
  done
  for p in "${ROOT_PATHS[@]}"; do
    [ -e "$p" ] || git ls-files --error-unmatch -- "$p" >/dev/null 2>&1 \
      || { echo "x root: -p $p does not exist"; FAIL=1; return; }
    stage+=("$p")
  done

  # What we are NOT taking, so nobody has to wonder where their file went.
  local left
  left="$(git status --porcelain | awk '{print $NF}' | while read -r f; do
    keep=1
    for s in "${stage[@]}"; do case "$f" in "$s"|"$s"/*) keep=0 ;; esac; done
    [ "$keep" = "1" ] && echo "$f"
  done)"

  if [ "${#stage[@]}" -eq 0 ] && [ "$ahead" = "0" ]; then
    echo ". root ($branch): no pointer moved, no -p path - skip"
    [ -n "$left" ] && echo "$left" | sed 's/^/      left alone: /'
    return
  fi

  if [ "$DRYRUN" = "1" ]; then
    echo "> root ($branch): WOULD commit:"
    for p in "${stage[@]}"; do echo "      $p"; done
    [ "$ahead" != "0" ] && echo "      ($ahead local commit(s) to push)"
    [ -n "$left" ] && echo "$left" | sed 's/^/      left alone: /'
    return
  fi

  if [ "${#stage[@]}" -gt 0 ]; then
    git add -- "${stage[@]}" || { echo "x root: git add failed"; FAIL=1; return; }
    if git diff --cached --quiet; then
      echo "  root: nothing staged after add"
    else
      # Commit only these paths: never sweep in something another session staged.
      printf '%s\n\n%s\n' "$MSG" "$TRAILER" | git commit -q -F - -- "${stage[@]}" \
        || { echo "x root: commit failed"; FAIL=1; return; }
      echo "  committed root (${#stage[@]} path(s))"
    fi
  fi
  [ -n "$left" ] && echo "$left" | sed 's/^/      left alone: /'

  if git push; then
    echo "ok root pushed"
  else
    echo "x root: push failed"
    FAIL=1
  fi
}

echo "== submodules (${#SUBS[@]}) =="
for p in "${SUBS[@]}"; do
  [ -n "$p" ] && process "$p" "$p"
done

echo "== root =="
process_root

if [ "$DRYRUN" = "1" ]; then
  echo
  echo "(dry-run - pass -m \"message\" to actually commit & push)"
fi
exit $FAIL
