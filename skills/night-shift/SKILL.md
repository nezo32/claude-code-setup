---
name: night-shift
description: Autonomous overnight mode - the owner is away (asleep) and wants the night spent productively with no waiting on them. A strong-model arbiter plans parallel branches with caps, fallbacks and a backlog; progress is checked by output files; forks are decided by the arbiter instead of asking; anything that truly needs the owner goes into one morning question batch. Use when the user types /night-shift or says "night shift", "work through the night", "don't wait for my answers", "keep going on your own until morning".
argument-hint: <goals for the night; permissions: GPU yes/no, budget $, may view outputs yes/no, morning time>
---

# Night shift: autonomous until morning

Owner's brief: $ARGUMENTS

Goal: in the morning the owner finds the most finished, verified, pushed work possible, plus one short report with everything that needs them. **A question for the owner is never a stop**: write it down, take the safe default, keep working on something else.

## 0. Start (about 10 minutes; no blocking questions from here until morning)

1. Read `CLAUDE.md`, the current-state / status file, the newest state or precompact file, the latest decisions-log rows, and `git worktree list`.
2. **Permissions come only from the brief and standing decisions. A missing permission means the safe default, not a question.**
   - Compute (local GPU, long jobs): whatever the brief or the project's standing rule says. The go-ahead ends at the morning time.
   - Money: a night cap (the project's default, e.g. a small fixed sum across all providers) unless the brief names another figure. Even with no cap, every spend goes to the spend ledger and every cloud machine is terminated.
   - Viewing outputs: nobody opens media unless the brief grants it for this night.
3. Create `docs/NIGHT-<date>.md` (or `work/<date>_night/log.md`): start time, permissions as read, cap, streams, queue, an empty "Morning questions" section.
4. Arm a heartbeat so the session never idles: a recurring scheduled prompt every 20 to 30 minutes (or a monitor loop on the branch finish markers): "night-shift heartbeat: check branches by their output files, merge what passed, launch the next queued tasks". Delete it at the end.
5. Reply to the owner in one or two lines, in their language: shift started, what runs, where the morning report will be.

## 1. Night plan by the arbiter

One `fable` agent writes `00_night_plan.md` from the brief, the status file and the open experiments:
- **Branches that run in parallel** (at least two when the night has more than one goal), each with a recipe (hypothesis, one variable, pilot, numeric gates, cap, stop rule) and a **finish signal** (a file or marker).
- **A fallback per branch**: what it does when blocked or failing its gates (smaller step, another variable, analysis of the results so far). Never "wait for the owner".
- **A backlog** of at least three items (tests, tool hardening, metric calibration, morning packages, docs that contradict the decisions log) to pull when branches finish early or block.
- A budget table per branch summing to at most the night cap; at most two variants per hypothesis.

## 2. Rules for the night

- **Maximum safe parallelism.** One worktree per stream, disjoint files. When an agent finishes: verify its claim (gate output, commit exists), merge on the gate, launch the next task at once.
- **Chain long jobs by completion markers** (a sentinel file or a log line), never by matching process command lines.
- **Safety stays**: gates before every merge, the rules in `CLAUDE.md`, no destructive git, no publishing or deploying unless already authorised, resource limits respected, the two-runs-per-hypothesis rule holds as by day.
- **Agents can be wrong**: check reports against diffs and gate output before merging. A failed gate goes to a fixer agent, never skipped.
- Commit and push after every finished branch (if the project allows it), so the morning `git log` tells the story.
- **Context**: run long. If a compaction comes, the night log plus the status file are the resume point; keep them current after every merge.

## 3. Forks and blocks: never stall

| Situation | Do |
|---|---|
| A choice the owner would normally make inside approved rules (winner, recipe, next variant, technical design) | `fable` arbiter writes `NN_decision_<topic>.md`; act on it; record it in the decisions log marked "orchestrator + Fable, night" |
| Needs the owner only: non-negotiables, canon/brand, spend over cap, deleting protected data, publishing, accounts, 2FA, licences | append to "Morning questions" (question, recommended option, the arbiter's view, what is ready either way); take the safe default; switch branch or pull from the backlog |
| An owner's eye verdict is needed (taste, "is it right") | do not wait: proceed on numeric gates, build the morning package; borderline items go in with their numbers |
| A branch failed its gates twice | stop that hypothesis, write the result, take its fallback or a backlog item |
| An agent is stuck on a permission prompt or silent for more than 30 minutes | restart it with a different step; note it for the morning |
| The cap is reached | stop paid work; finish CPU work and the report |

An idle resource the brief allowed is a planning bug: give it the next backlog item.

## 4. Watch

A finished background task wakes the session by itself; a stuck one does not. On each heartbeat check every branch by **new output files**, not by agent messages, and write one line to the log (time, branch, last file, spend so far). Then:

1. Read and verify the result (gate exit code, `git log`, report file).
2. Merge / fix / review as the plan says; push.
3. Update the night log: done, running, queue, morning questions.
4. Launch the next tasks so the number of running streams stays high.
5. Queue empty -> next items of the project plan; plan exhausted -> reviews, tests, tech debt, docs.

## 5. Morning (at the time in the brief, or the project default)

- Stop paid and compute work; the compute go-ahead ends with the night (stop services you started and verify).
- Delete the heartbeat. Update the status file.
- A `writer` agent writes the night report (one screen, owner's language): result per branch with numbers and file links, arbiter decisions taken, spend vs. cap, what is ready to judge, failures, temporary stand-ins. Nothing is marked "checked by eye" unless it was.
- When the owner is back: the morning questions as ONE question batch, recommended option first, each with the default already used.
- Run `/precompact`; commit and push; one short message to the owner: report path, spend, number of questions.

## Never at night

Change non-negotiables or canon. Publish or deploy without prior authorisation. Open media without the brief's grant. Exceed the cap. Delete protected data. Force-push. Put secret values anywhere.
