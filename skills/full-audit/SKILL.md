---
name: full-audit
description: Exhaustive parallel-subagent audit of a codebase - decompose it into the smallest auditable chunks (per package, per endpoint group, per UI layer), fan out one read-only subagent per chunk plus cross-cutting security / architecture / contract / infra passes, have every subagent write findings to disk instead of returning them, adversarially verify the severe ones, compose one ranked artifact, then STOP for the user before fixing anything. Use when asked to "audit the project", "full audit", "find all bugs", "review the whole codebase", or "security and architecture audit".
---

# Full audit: decompose -> fan out -> verify -> compose -> gate

Goal: a **complete, valid audit of the current state of the product**: every module, endpoint, component, exported function and business rule, checked for correctness, edge cases, sanity of the rule itself, security, and architecture (readable, scalable, modular).

Phases, with a **hard human gate** before anything is edited:

1. **Decompose.** Enumerate the real structure and split it into the smallest auditable chunks. Coverage is decided here.
2. **Fan out (read-only).** One subagent per chunk, plus cross-cutting passes. **Subagents write findings to a shared directory; they do not return them.** That keeps coverage at 100% without overflowing the orchestrator's context.
3. **Verify and compose.** Adversarially verify the severe findings, dedupe, compose one ranked artifact. Then STOP.
4. **Fix** (only what the user approved).

**Do not edit product code in phases 1 to 3.** Other agents may be working in the tree concurrently; the audit stays read-only until the user approves.

## The findings directory (create it first)

```
.audit/<YYYY-MM-DD>/plan.md
.audit/<YYYY-MM-DD>/findings/<chunk-id>.md
.audit/<YYYY-MM-DD>/verified/<finding-id>.md
.audit/<YYYY-MM-DD>/AUDIT.md
```

Add `.audit/` to `.gitignore` if it is not there (the one write allowed before the gate; it touches no product code). One chunk = one file = one subagent. Never let two subagents write the same file.

Every findings file uses this exact shape so compose can parse it:

```markdown
# <chunk-id>
scope: <paths/globs this agent actually read>
verdict: findings | clean
coverage-gaps: <anything in scope it could not read, or "none">

## F-<chunk-id>-01
severity: critical | high | medium | low
category: bug | logic | edge-case | security | architecture | readability | scalability
location: path/to/file.ext:123
what: <the defect, one or two sentences>
why: <concrete failure scenario: inputs/state -> wrong output, leak, or crash>
fix: <the minimal correct change>
confidence: high | medium | low
```

A genuinely clean chunk writes `verdict: clean` with no findings. Padding the file to look thorough is worse than an empty one.

## Phase 1: Decompose

**Read the tree first**, so the split matches reality. Then split each module by its natural seams:

| Kind of module | Split by |
|---|---|
| Backend service | one chunk per package **group** (auth, authz/roles, billing, persistence, messaging, HTTP layer, config/observability...) |
| Worker / pipeline | ingest, processing, external providers, storage, results/notify |
| Frontend | one chunk per architectural layer (routing/SSR/middleware, pages, widgets, features, entities, shared, i18n) |
| Sidecars / scripts | input validation and DoS surface, resource lifecycle, service layer |
| Test suites | what the suites actually assert vs. what they claim to cover |

Plus **dedicated cross-cutting chunks**. The severe bugs live at the seams; never skip these on a full audit:

- `xcut-contract-sync`: a wire contract duplicated per language or per service. Trace one request end to end; a field added or renamed in one copy but not all is a real bug.
- `xcut-authz-e2e`: follow a request from the client through the API to a tenant- or user-scoped resource. Missing checks, IDOR, tenant-isolation gaps, privilege escalation.
- `xcut-security`: only lens is security across the stack: secrets handling, sessions, input validation, SSRF, injection, XSS/CSRF, rate limits, file upload/download, object-store access, exposed ports and trust boundaries.
- `xcut-architecture`: boundaries, coupling, layering violations, duplication, dependency direction. Split by language if one agent would read too much.
- `xcut-api-surface`: enumerate **every** endpoint from the router; each has authn, authz, validation, error handling and a matching spec entry.
- `xcut-ops` and `infra-*`: compose files, env templates, CI, container files, manifests (as separate chunks per overlay): resource limits, probes, plaintext secrets (critical), RBAC, network policy, image tags, drift between environments.

Write the chunk list to `plan.md` (chunk-id -> scope) before launching. That file is the coverage contract: anything not in it was not audited, and the final artifact must say so.

Scale to the ask: "audit everything" -> all chunks. A narrower ask ("security only", "audit the API") -> just those, plus at least one cross-cutting pass for anything spanning modules.

## Phase 2: Fan out (read-only, findings to disk)

Launch subagents **in batches, several Agent calls per message**. For a whole product that is dozens of agents; that is the point. Same charter for each, scoped to its chunk:

> You are auditing chunk `<chunk-id>`: `<exact scope paths>`.
> **Read-only. Do not edit, create or delete any file except your one findings file. No git mutations, no builds that write, no starting services.**
> Read *every* file in your scope. For each endpoint, component, exported function and business rule, check correctness, logic and edge cases, sanity of the rule itself, security, and whether the code is readable, scalable and modular. Note how your chunk couples to the rest.
> **Do not return findings in your reply.** Write them to `.audit/<date>/findings/<chunk-id>.md` in the exact template from the full-audit skill. Every finding needs a real `file:line` and a concrete failure scenario; if you cannot say how it fails, it is not a finding. Write `verdict: clean` if the chunk is clean; do not invent findings.
> Reply with only: the file path, the finding count by severity, and any coverage gaps.

If a chunk turns out bigger than one agent can honestly read, it says so in `coverage-gaps:`; split it and re-launch. Never accept partial coverage silently.

## Phase 3: Verify and compose

1. **Check coverage.** Every chunk in `plan.md` has a findings file. Missing or gap-flagged chunks are re-launched first.
2. **Adversarially verify.** For every `critical`/`high` finding and every `confidence: low` one, launch a `skeptic` agent prompted to **refute** it, defaulting to "not a real issue" when uncertain. Verdicts go to `verified/<finding-id>.md`. Drop or downgrade what does not survive. Not optional: plausible-but-wrong findings are the main failure mode of a fan-out audit.
3. **Dedupe.** The same defect surfaces from a module agent and a cross-cutting agent. Merge into one entry citing both.
4. **Compose `AUDIT.md`**: executive summary (what is healthy, what is not, top risks); findings grouped critical -> low, each with id, `file:line`, impact, proposed change; an architecture section (boundaries, coupling, verdict per module); coverage (chunks audited, anything not covered).

Present a skimmable summary in chat: lead with the criticals and the counts.

## The gate: wait for the user

**STOP and ask which findings to fix.** Let them approve all, a subset, or none; record deferred and accepted-risk items in `AUDIT.md`. Do not touch the tree until they answer.

## Phase 4: Fix (approved findings only, in parallel)

- Group approved findings by module and fan out one fix agent per module, in one message. Each gets only its module's findings with `file:line` and the agreed fix.
- **Isolate parallel writers**: two agents never touch the same file at once; serialise or use worktree isolation. Fixes to a shared contract land in every copy together.
- Re-check each target still looks as audited before writing; if it moved, re-verify.
- Run the affected gates (`pre-prod-check`). Re-audit any non-trivial fix.

Report: what was fixed, what was deferred or accepted, gate results.

## Gotchas

- **Read-only means read-only until the gate.** A subagent that "helpfully" fixes something breaks the gate and collides with others in the tree.
- **Findings go to disk, not to the reply.** The orchestrator's context is the scarce resource; it must survive to compose.
- **Decompose smaller than feels necessary.** An agent given a whole service skims; one given a single package reads every line.
- **Formatting noise is not a finding** (for example line-ending differences on a Windows checkout). Use the real compiler and linter signals.
- **Empty is a valid result.**

## Relationship to other skills

- `pre-prod-check` runs the **mechanical** gates (build, lint, test, e2e) every time. This skill is the **deep** audit with a human gate. A real release sign-off runs both, and re-runs the mechanical gates after the audit's fixes land.
- `commit-push` lands the fixes.
