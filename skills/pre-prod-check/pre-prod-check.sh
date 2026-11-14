#!/usr/bin/env bash
# pre-prod-check.sh - run every mechanical release gate, one PASS/FAIL report.
#
# Phases (in order; pick a subset with flags):
#   static  STATIC_GATES from the config (build, lint, typecheck, unit tests,
#           CI parity checks). A gate CI enforces that cannot run here is a
#           loud WARN, repeated in the summary, never a silent skip.
#   audit   built in: no tracked secret env files, no focused/skipped tests,
#           optional vacuous-test check, every module clean and on a branch,
#           TODO/FIXME count.
#   up      UP_CMD if UP_CHECK fails, then READY_CMD (readiness preflight).
#   e2e     E2E_GATES; with --full also E2E_FULL_GATES.
#
# Usage:
#   pre-prod-check.sh               # static + audit + up + e2e (fast set)
#   pre-prod-check.sh --full        # everything incl. slow/destructive suites
#   pre-prod-check.sh --static | --audit | --up | --e2e [--full]
#
# Config: $PRE_PROD_CONF, else .claude/pre-prod.conf (see pre-prod.conf.example).
# Exit non-zero if any selected gate fails.

set -uo pipefail
ROOT="$(git rev-parse --show-toplevel)" || exit 1
cd "$ROOT" || exit 1

CONF="${PRE_PROD_CONF:-$ROOT/.claude/pre-prod.conf}"
[ -f "$CONF" ] || { echo "no config at $CONF (copy pre-prod.conf.example)" >&2; exit 2; }
MODULES="" ; TEST_DIRS="" ; VACUOUS_CHECK="" ; SOURCE_DIRS=""
UP_CHECK="false" ; UP_CMD="" ; READY_CMD=""
STATIC_GATES=() ; E2E_GATES=() ; E2E_FULL_GATES=() ; KNOWN_GAPS=()
# shellcheck disable=SC1090
. "$CONF"

PASS=0; FAIL=0; NOTE=0; WARN=0; WARNINGS=""
ok()   { echo "  ok $*"; PASS=$((PASS+1)); }
bad()  { echo "  x  $*"; FAIL=$((FAIL+1)); }
note() { echo "  .  $*"; NOTE=$((NOTE+1)); }
hdr()  { echo; echo "== $* =="; }
# warn: a gate CI ENFORCES that this run could not. Repeated in the summary so it
# cannot scroll away. Never changes the exit code.
warn() {
  echo "  !  $*"
  WARN=$((WARN+1))
  WARNINGS="$WARNINGS
      ! $*"
}

# run <label> <cmd> : PASS on exit 0, else FAIL with the last 15 lines.
run() {
  local label="$1" cmd="$2" out
  if out="$(bash -c "$cmd" 2>&1)"; then ok "$label"
  else bad "$label"; echo "$out" | tail -15 | sed 's/^/      /'; fi
}

# gate "label|cmd[|requires=bin]"
gate() {
  local spec="$1" label cmd req=""
  label="${spec%%|*}"; cmd="${spec#*|}"
  case "$cmd" in *"|requires="*) req="${cmd##*|requires=}"; cmd="${cmd%|requires=*}" ;; esac
  if [ -n "$req" ] && ! command -v "$req" >/dev/null 2>&1; then
    warn "$label NOT RUN: '$req' is not installed here, but CI enforces it."
    return
  fi
  run "$label" "$cmd"
}

want_static=0 want_audit=0 want_up=0 want_e2e=0 full=0
while [ $# -gt 0 ]; do
  case "$1" in
    --static) want_static=1 ;;
    --audit)  want_audit=1 ;;
    --up)     want_up=1 ;;
    --e2e)    want_e2e=1 ;;
    --full)   full=1 ;;
    -h|--help) sed -n '2,22p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
  shift
done
if [ $((want_static+want_audit+want_up+want_e2e)) -eq 0 ]; then
  want_static=1; want_audit=1; want_up=1; want_e2e=1
fi

# static
if [ "$want_static" = 1 ]; then
  hdr "static"
  for g in "${STATIC_GATES[@]}"; do gate "$g"; done
fi

# audit
if [ "$want_audit" = 1 ]; then
  hdr "audit: production readiness"

  # 1. No real secret env files tracked (only *.example / *.sample may be).
  leaked=""
  for m in . $MODULES; do
    [ -d "$m" ] || continue
    leaked="$leaked
$(git -C "$m" ls-files 2>/dev/null | grep -E '(^|/)\.?[^/]*\.env(\..+)?$|(^|/)\.env$' | grep -vE '\.(example|sample|template)$' || true)"
  done
  leaked="$(echo "$leaked" | grep -v '^$' || true)"
  if [ -z "$leaked" ]; then ok "no secret env files tracked in git"
  else bad "secret env files are tracked: untrack AND rotate:"; echo "$leaked" | sed 's/^/      /'; fi

  # 2. Focused / disabled tests. `.only` always blocks; `.skip("name", ...)` disables a
  #    declared test and blocks; `.skip(<expression>, ...)` is a runtime guard: allowed.
  #    scripts/ is excluded: a tool that detects `.only` has to name it.
  if [ -n "$TEST_DIRS" ]; then
    # shellcheck disable=SC2086
    foc="$(grep -rnE '\b(it|test|describe)\.only\b|\b(it|test|describe)\.skip\s*\(\s*("|'"'"'|`)' \
          $TEST_DIRS 2>/dev/null --include='*.js' --include='*.mjs' --include='*.ts' --include='*.tsx' \
          --include='*_test.go' --include='test_*.py' \
          --exclude-dir=node_modules --exclude-dir=scripts || true)"
    if [ -z "$foc" ]; then ok "no .only / named .skip left in suites"
    else bad "focused/disabled tests found:"; echo "$foc" | sed 's/^/      /'; fi
  else
    note "TEST_DIRS not set: focused-test scan skipped"
  fi

  # 3. Vacuous tests (pass having asserted nothing).
  if [ -n "$VACUOUS_CHECK" ]; then run "no vacuous tests" "$VACUOUS_CHECK"
  else note "VACUOUS_CHECK not set"; fi

  # 4. Every module committed and on a branch.
  for m in $MODULES .; do
    [ -d "$m" ] || continue
    label="$m"; [ "$m" = "." ] && label="root"
    br="$(git -C "$m" rev-parse --abbrev-ref HEAD 2>/dev/null)"
    dirty="$(git -C "$m" status --porcelain 2>/dev/null)"
    if [ "$br" = "HEAD" ]; then bad "$label: detached HEAD"
    elif [ -n "$dirty" ]; then bad "$label: uncommitted changes"
    else ok "$label: clean on '$br'"; fi
  done

  # 5. Informational TODO count.
  if [ -n "$SOURCE_DIRS" ]; then
    # shellcheck disable=SC2086
    todos="$(grep -rnE 'TODO|FIXME|HACK|XXX' $SOURCE_DIRS 2>/dev/null --exclude-dir=node_modules | wc -l | tr -d ' ')"
    note "TODO/FIXME/HACK markers in source: $todos (review before release)"
  fi
fi

# up
if [ "$want_up" = 1 ]; then
  hdr "up: stack + readiness"
  if bash -c "$UP_CHECK" >/dev/null 2>&1; then ok "stack already running"
  elif [ -n "$UP_CMD" ]; then run "start stack" "$UP_CMD"
  else note "UP_CMD not set"; fi
  if [ -n "$READY_CMD" ]; then run "readiness preflight" "$READY_CMD"
  else note "READY_CMD not set"; fi
fi

# e2e
if [ "$want_e2e" = 1 ]; then
  hdr "e2e"
  for g in "${E2E_GATES[@]}"; do gate "$g"; done
  if [ "$full" = 1 ]; then
    for g in "${E2E_FULL_GATES[@]}"; do gate "$g"; done
  elif [ "${#E2E_FULL_GATES[@]}" -gt 0 ]; then
    note "${#E2E_FULL_GATES[@]} slow suite(s) skipped (pass --full)"
  fi
  for gap in "${KNOWN_GAPS[@]}"; do warn "known gap: $gap"; done
fi

# summary
hdr "summary"
echo "  PASS=$PASS  FAIL=$FAIL  NOTE=$NOTE  WARN=$WARN"
if [ "$WARN" -gt 0 ]; then
  echo
  echo "  ! $WARN gate(s) were NOT run here; a green result does not cover them:"
  printf '%s\n' "$WARNINGS"
fi
echo "  note: mechanical gates only; a release sign-off also runs the full-audit skill."
if [ "$FAIL" -gt 0 ]; then echo "  x NOT ready for production ($FAIL failing)"; exit 1; fi
echo "  ok all selected checks passed"
