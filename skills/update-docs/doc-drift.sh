#!/usr/bin/env bash
# doc-drift.sh - surface where the docs may have fallen out of sync with the code.
# Read-only: it reports, it does not edit. It cannot judge prose; it gives you the
# facts to judge with.
#
#   1. Routes found in the router source vs. which docs mention each one.
#   2. Request fields that were removed but still appear in docs.
#   3. What changed recently per module (so you know which docs to revisit).
#   4. Which expected docs exist.
#
# Configure with env vars (see SKILL.md): DOC_FILES, DOC_ROUTE_FILES,
# DOC_ROUTE_REGEX, DOC_REMOVED_FIELDS, DOC_MODULES.
#
# Usage:  bash .claude/skills/update-docs/doc-drift.sh

set -uo pipefail
ROOT="$(git rev-parse --show-toplevel)" || exit 1
cd "$ROOT" || exit 1

read -r -a DOCS <<< "${DOC_FILES:-README.md RUNBOOK.md}"
ROUTE_REGEX="${DOC_ROUTE_REGEX:-\"(GET|POST|PUT|DELETE|PATCH) /[^\"]+\"}"
read -r -a REMOVED <<< "${DOC_REMOVED_FIELDS:-}"
if [ -n "${DOC_MODULES:-}" ]; then
  read -r -a MODULES <<< "$DOC_MODULES"
else
  MODULES=(.)
  if [ -f .gitmodules ]; then
    while read -r m; do MODULES+=("$m"); done < <(git config --file .gitmodules --get-regexp '\.path$' | awk '{print $2}')
  fi
fi

hdr() { echo; echo "== $* =="; }

# 1. Route coverage
hdr "routes: code vs docs"
if [ -z "${DOC_ROUTE_FILES:-}" ]; then
  echo "  (DOC_ROUTE_FILES not set: skipping route coverage)"
else
  # shellcheck disable=SC2086  # globs are intended to expand
  routes="$(grep -hoE "$ROUTE_REGEX" $DOC_ROUTE_FILES 2>/dev/null | tr -d '"' | sort -u)"
  if [ -z "$routes" ]; then
    echo "  (no routes matched in: $DOC_ROUTE_FILES)"
  else
    printf "  %-50s %s\n" "ROUTE" "MENTIONED IN"
    while IFS= read -r r; do
      path="${r#* }"   # drop the method, keep the path
      found=""
      for d in "${DOCS[@]}"; do
        [ -f "$d" ] || continue
        grep -qF "$path" "$d" && found="$found ${d##*/}"
      done
      [ -z "$found" ] && found=" *** NONE ***"
      printf "  %-50s%s\n" "$r" "$found"
    done <<< "$routes"
  fi
fi

# 2. Removed request fields still in docs
hdr "removed request fields still shown in docs"
if [ "${#REMOVED[@]}" -eq 0 ]; then
  echo "  (DOC_REMOVED_FIELDS not set)"
else
  for f in "${REMOVED[@]}"; do
    hits=""
    for d in "${DOCS[@]}"; do
      [ -f "$d" ] && grep -q "\"$f\"" "$d" && hits="$hits $d"
    done
    [ -n "$hits" ] && echo "  x \"$f\" was removed but still appears in:$hits"
  done
  echo "  (a removed field in a REQUEST example is drift; in a RESPONSE schema it may be fine)"
fi

# 3. Recent changes per module
hdr "recent changes (last 5 commits per module + working-tree state)"
for m in "${MODULES[@]}"; do
  label="$m"; [ "$m" = "." ] && label="root"
  echo "  --- $label ---"
  git -C "$m" log --oneline -5 2>/dev/null | sed 's/^/    /'
  dirty="$(git -C "$m" status --porcelain 2>/dev/null)"
  [ -n "$dirty" ] && echo "    (uncommitted:)" && echo "$dirty" | sed 's/^/      /'
done

# 4. Docs inventory
hdr "docs inventory"
for d in "${DOCS[@]}"; do
  [ -f "$d" ] && echo "  ok $d" || echo "  x missing: $d"
done

echo
echo "Next: edit the drifted docs, then validate (parse the OpenAPI/collection files, re-run this scanner)."
