---
name: pre-prod-check
description: One driver that runs every mechanical gate that must be green before a release - static (build, lint, typecheck, unit tests per module), a production-readiness audit (no tracked secrets, no focused or vacuous tests, every module clean and on a branch), bring the stack up with a readiness preflight, then the end-to-end suites. Prints PASS / FAIL / NOTE / WARN and exits non-zero on any failure; gates CI enforces but this run could not are repeated in the summary. Use when asked to "run all tests", "check before release", "is it ready for prod", or as the final pre-deploy gate.
---

# Pre-production check

One driver, `.claude/skills/pre-prod-check/pre-prod-check.sh`, runs the gates from a per-project config file and produces a single PASS/FAIL report with a non-zero exit on any failure.

## Setup (once per project)

Copy `pre-prod.conf.example` to `.claude/pre-prod.conf` and fill in your gates. Each gate is one line: `"label|command"`. Add `|requires=<binary>` to a gate CI enforces but that needs a tool which may be missing locally: when the tool is absent the gate becomes a loud **WARN** instead of silently disappearing.

## Run

```bash
bash .claude/skills/pre-prod-check/pre-prod-check.sh            # static + audit + up + e2e (fast set)
bash .claude/skills/pre-prod-check/pre-prod-check.sh --full     # + the slow / destructive suites
bash .claude/skills/pre-prod-check/pre-prod-check.sh --static   # one phase while iterating
bash .claude/skills/pre-prod-check/pre-prod-check.sh --audit
bash .claude/skills/pre-prod-check/pre-prod-check.sh --up
bash .claude/skills/pre-prod-check/pre-prod-check.sh --e2e [--full]
```

| Phase | Gates |
|---|---|
| **static** | `STATIC_GATES` from the config: build, vet/lint, typecheck, unit tests, formatter check, lockfile in sync, generated code has no drift, spec copies byte-identical |
| **audit** | built in: no real env files tracked in git (only `*.example`); no `.only` and no `.skip("name", ...)` left in suites; optional vacuous-test checker; every module clean and on a branch; TODO/FIXME count (informational) |
| **up** | `UP_CMD` if the stack is not running (`UP_CHECK` decides), then `READY_CMD` (a readiness preflight against every service) |
| **e2e** | `E2E_GATES` always; `E2E_FULL_GATES` with `--full` (slow, serial, failure-injection suites) |

For the frontend (or any module with a CI verify job), also run `ci-gates.sh`: it reads the `npm run ...` lines straight out of the CI file's job and runs them in order, so the local list cannot drift from CI.

```bash
CI_FILE=frontend/.gitlab-ci.yml CI_JOB=verify bash .claude/skills/pre-prod-check/ci-gates.sh frontend
LIST=1 CI_FILE=... bash .claude/skills/pre-prod-check/ci-gates.sh frontend   # just print the gates
```

## What the agent still does by hand

The driver covers mechanical gates. Before signing off a release, also:

- **Read the diff of each changed module** for sanity and consistency with its neighbours. Build passing is not good code.
- **Confirm contract sync** when a wire contract is duplicated across languages or services.
- **Confirm docs match behaviour** (`update-docs`).
- **Re-read the known-open findings list** and consciously accept or fix each.

The deep correctness and security review is the `full-audit` skill. A release sign-off runs both, and re-runs the affected gates here after the audit's fixes land.

## Lessons baked into the driver

- **A local gate that checks less than CI is worse than none, because it is trusted.** Releases have been tagged on a green local run and then never built, because CI ran a formatter check, a schema-drift check or a linter that the local driver skipped. So the config should list *every* blocking CI gate, and anything that cannot run locally is a WARN, repeated verbatim in the summary next to `PASS=n FAIL=0`. Warnings never change the exit code: a warning that failed the run would be routed around within a week.
- **"Not applicable" (NOTE) and "CI checks this and we did not" (WARN) are different things** and are printed differently.
- **A missing tool is not a failed check.** Probe for the parser or binary first; an unrun check must say it did not run, never that it failed.
- **The focused-test gate must not cry wolf.** `.only` is always a blocker; `.skip("literal name", ...)` disables a declared test and is a blocker; `.skip(<expression>, ...)` is a runtime capability guard and is allowed. Tooling directories are excluded: a checker that detects `.only` has to name it. A gate that is always red is a gate people learn to scroll past.
- **Vacuous tests.** Many runners count a test whose body hits a bare `return` as PASSED. Suites that skip their whole body unless an env var is set, invoked by a bare test-runner line that sets no env, are counted as coverage while executing nothing. Run those through the script that sets the variable, and grep new suites for module-level env gates.
- **Line endings are a property of the checkout, not the OS.** Detect CRLF with `git ls-files --eol`, not `grep $'\r'` (under Git Bash the latter lists every file and silently disables the gate).
- **Don't run the driver twice at once**; parallel builds on one module contend on the build cache and look hung.
- **Background output buffers until exit.** Poll for the `== summary ==` line.

## Interpreting the result

Exit 0 with `FAIL=0` = ready. An "uncommitted changes" line in the audit is expected while work is in flight: commit and re-run. Any other failure is a real blocker; the driver prints the last 15 lines of the failing command inline.
