---
name: precompact
description: Save the session's working state - goal, user authorizations, decisions with their reasons, every changed file, running agents and background tasks, the remaining plan - to a durable file BEFORE the context is compacted, then hand the user the exact /compact line that makes the next context reload it. Use when the user types /precompact, says "prepare for compact" or "save context", before a planned pause, or when the context is getting long.
argument-hint: "[short note on what to keep in focus]"
---

# precompact: save state, then compact

Note from the user (may be empty): $ARGUMENTS

`/compact` is a built-in CLI command; this skill cannot run it. It writes the state file, checks it, and ends by giving the user one ready-to-send `/compact` line. A summary loses detail; this file is what survives exactly.

Write only facts from this session. Never invent decisions or steps.

## 1. Pick the file

- The project keeps a status doc with a resume section (e.g. `docs/STATUS.md` "Resume point") -> update that section, and add new decisions to the decisions log (step 3b).
- Otherwise, the project has a git-ignored `.plan/` -> `.plan/<current-task>/STATE.md` (the task's existing plan dir, else `.plan/_session/STATE.md`).
- Otherwise -> the session scratchpad, `STATE-<yyyy-mm-dd-HHMM>.md`.
- Overwrite the previous STATE.md of the same task: it is a snapshot, not a log.
- Never put secrets in it. Name where they live instead.

## 2. Gather facts with tools, not from memory

- **Changed files**, per repo AND per worktree you used: `git -C <repo> status --short`, `git -C <repo> log --oneline <base>..HEAD`, `git worktree list`. Mark each file committed (sha) / staged / uncommitted, and whether it is yours or was already dirty (someone else's: leave it alone).
- **Pushed / tagged / deployed**: branch vs. remote, tags created, what runs in production (only what you verified).
- **Running work**: background shells (id and what), subagents (id, role, model, slice, status), servers or containers you started (port, how to stop).
- **External state you changed**: cloud resources, repos created, production changes.
- **Spend this session**: provider balances or ledger rows before and after, from logs and reports you already have.
- **The user's messages this session**: every decision, correction, approval, rejection and permission, with its scope (e.g. "may view outputs tonight only"). Quote verbatim where the wording matters. Read agent output files only if a needed line is missing; never dump transcripts.

## 3. Write the file: this structure, terse, facts over prose

```markdown
# STATE: <task>: <UTC timestamp>
## Goal
<one paragraph: what the user wants, in their terms>
## User authorizations and standing instructions
- <near-verbatim quote + date> (e.g. "deploy allowed after the gates pass")
## Decisions (and why)
- <decision>: <reason / evidence>: <who decided: user | me>
## Rejected options
- <option>: <why not>
## Corrections and prohibitions
- <what the user corrected or forbade, so it is not repeated>: <memory or rule file it now lives in>
## Changed files
| repo/worktree | file | state (sha / uncommitted) | note |
## Done and verified
- <item>: <how verified>
## In flight
- <agent/task id>: <role, model>: <what it is doing>: <what to do with its result>
## Next steps (ordered)
1. <exact command or file>  [needs the user's go: spend over cap / compute / canon change]
## Open questions / blocked on user
- <question>: <options, recommended first>
## Numbers
- <balances, spend, key QC numbers that later decisions depend on>
## Gotchas learned this session
- <trap>: <how to avoid it>
```

Keep it under about 150 lines; link to longer reports instead of copying them.

### 3b. Decisions log (if the project keeps one)

Log every decision of this session that is not recorded yet, now, before compacting. One new row per decision: next free id, today's date, the decision in one sentence, the source (user Q&A, report path, review). A change to an earlier decision is a new row naming the row it overrides.

## 4. Check it

Re-read the file once. Every "Next steps" item must be actionable without the conversation (files, command, acceptance check); every in-flight id must be real. If something durable was learned (a user correction, a non-obvious project fact), also save it to memory: the state file is per task, memory is permanent. Do not commit unless the user asked.

## 5. Hand over

Reply with the file's absolute path, a 3-line summary, and this line for the user to send (fill in the path):

```
/compact Keep: goal, user authorizations, decisions, in-flight agent/task ids, next steps. After compacting, first Read <absolute path to STATE.md> and continue from "Next steps".
```
