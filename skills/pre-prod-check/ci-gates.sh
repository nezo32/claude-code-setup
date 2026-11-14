#!/usr/bin/env bash
# ci-gates.sh - run a module's REAL CI gate list locally, in CI order.
#
# Why: "local green" has repeatedly been "CI red" because the local list was a
# hand-maintained subset (a formatter check, a generated-file freshness check, a
# lockfile the CI's package-manager version rejects). A red verify job often
# leaves the deploy job "skipped", which looks like "waiting for a human". So
# this script keeps no list of its own: it READS the `npm|pnpm|yarn run <x>`
# lines out of one job in the CI file and runs exactly those.
#
# Usage:
#   CI_FILE=<path> [CI_JOB=verify] ci-gates.sh [module-dir]
#   LIST=1 ...          print the extracted gate list and exit
#   SKIP="build e2e"    skip named gates (say so in your report)
#   CI_INSTALL=1        run a clean install first (validates the lockfile as CI does)
#   MIN_GATES=3         fail if fewer gates are extracted (the CI file changed shape)
#
# Notes:
#   * Gates that compare against HEAD pass only after the change is committed.
#   * A build writes output dirs: do not run it under a live dev server in the
#     same directory. Use a clean git worktree when servers are up.
#   * Run this once from the orchestrator, never from parallel worker agents.
set -u

DIR="${1:-.}"
CI_FILE="${CI_FILE:-$DIR/.gitlab-ci.yml}"
JOB="${CI_JOB:-verify}"
MIN="${MIN_GATES:-3}"
[ -f "$CI_FILE" ] || { echo "ci-gates: $CI_FILE not found" >&2; exit 2; }

# Everything between the top-level `<job>:` key and the next top-level key.
job="$(awk -v j="^${JOB}:" '$0 ~ j {on=1; next} on && /^[A-Za-z_.:-]+:/ {on=0} on' "$CI_FILE")"
pm="$(printf '%s\n' "$job" | sed -n 's/^[[:space:]]*-[[:space:]]*\(npm\|pnpm\|yarn\) run .*/\1/p' | head -1)"
pm="${pm:-npm}"
mapfile -t gates < <(printf '%s\n' "$job" | sed -n 's/^[[:space:]]*-[[:space:]]*\(npm\|pnpm\|yarn\) run \([A-Za-z0-9:_-]*\).*$/\2/p')

# An extractor that found nothing must FAIL, not pass.
if [ "${#gates[@]}" -lt "$MIN" ]; then
  echo "ci-gates: extracted only ${#gates[@]} gate(s) from job '$JOB' in $CI_FILE (expected >= $MIN)." >&2
  echo "  The job changed shape; fix the extraction before trusting this script." >&2
  exit 2
fi

if [ "${LIST:-0}" = "1" ]; then printf '%s\n' "${gates[@]}"; exit 0; fi
cd "$DIR" || exit 2
echo "ci-gates: ${#gates[@]} gates from $CI_FILE job '$JOB' @ $(git rev-parse --short HEAD 2>/dev/null)"
echo "  ${gates[*]}"

if [ "${CI_INSTALL:-0}" = "1" ]; then
  echo "-- clean install --"
  case "$pm" in
    npm)  npm ci --no-audit --no-fund ;;
    pnpm) pnpm install --frozen-lockfile ;;
    yarn) yarn install --frozen-lockfile ;;
  esac || { echo "x install"; exit 1; }
fi

fail=0; ran=0; skipped=()
for g in "${gates[@]}"; do
  case " ${SKIP:-} " in *" $g "*) skipped+=("$g"); continue;; esac
  log="$(mktemp)"
  start=$SECONDS
  if "$pm" run "$g" >"$log" 2>&1; then
    echo "ok $g ($((SECONDS - start))s)"
  else
    echo "x  $g ($((SECONDS - start))s), last lines:"
    tail -25 "$log" | sed 's/^/    /'
    fail=$((fail + 1))
  fi
  ran=$((ran + 1))
  rm -f "$log"
done

echo
echo "ci-gates: ran $ran of ${#gates[@]} gates, $fail failed${skipped:+, skipped: ${skipped[*]}}"
[ "$fail" -eq 0 ]
