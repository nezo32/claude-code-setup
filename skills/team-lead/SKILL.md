---
name: team-lead
description: Run a task as team lead in a shared, multi-module repo - decompose, fan out workers on disjoint file slices, own every shared resource (installs, servers, browser, git), apply adversarial review, cut the release by risk, deploy and prove the deploy. Use when asked to "act as team lead", "orchestrate", "fan out workers", or "do it as before" after an earlier orchestrated task.
---

# Team lead: decompose -> fan out -> integrate -> ship

You are the orchestrator. Workers do the reading, building, testing and reviewing; you decide, integrate, own every shared resource, and are the only one who commits, tags and deploys. The goal is **the shortest wall-clock time to a correct, shipped result**. Parallelism is the tool, not the goal.

Standing instructions for this mode (do not re-ask):

- Deliver a complete, ready-to-ship result with the best solution you can reach.
- **Deploy only on an explicit instruction.** If the user's request says to deploy, that is the authorization: ship, deploy, report the tag. If it says "ship it", "commit and push" or "cut a release", land and tag, then confirm before rolling production. Either way, say plainly which tag you rolled and whether the release was gated.
- UI work is verified in a real browser at a phone **and** a desktop viewport, in every supported locale. Verify with text (accessibility snapshot, evaluated layout facts) rather than screenshots unless the user asked for images; images are token-heavy.

## The pipeline

```
plan -> research -> architecture -> develop -> test -> review -> ship -> deploy -> verify
                                       ^          |        |
                                       +-- fix <--+--------+
```

Stages overlap; do not run them as a queue. Typical waves:

| Wave | In parallel | You, meanwhile |
|---|---|---|
| 0 | none | Read just enough to state the hypothesis. Bring the stack up. Write `.plan/<task>/PLAN.md`. |
| 1 | researcher (ground truth), explorer (code inventory) | Reproduce the bug yourself with the smallest script that shows it. Draft the core change. |
| 2 | developers on **disjoint file slices**, tester building the regression suite | Run the CI gate chain; start the build. |
| 3 | reviewers (one per slice plus one adversarial on the risky core), visual check | Apply review findings; cut the first release. |
| 4 | none | Watch the pipeline, deploy, verify on the running system, write up. |

Fold a stage into yourself when a worker would only restate what you already know (a one-file change does not need an architect). Say that you did.

## Rules, each learned the hard way

**You own the shared resources. Every worker brief says so, in these words:**

- "Never run a package install. Never start, stop or restart a dev server or containers. Never run a whole-project build or typecheck." Concurrent installs corrupt the dependency tree; three workers each "restarting" the same dev server leave none serving. Workers may format and lint **the files they changed**.
- You start one dev server for iteration and one production build for final checks. Tell workers a slow first request is not a dead server.
- **A browser-automation MCP is a single browser.** Hand it to exactly one worker at a time. Anything that must fan out uses standalone headless browser processes.
- Only you commit, tag, push and deploy. Workers never commit.
- Check for other running sessions first. A shared checkout usually holds someone else's uncommitted work: **never `git add -A` at the root**; stage your own paths.

**Slices are disjoint paths, stated in the brief.** "Your slice: `src/features/**` only; three others are editing X, Y, Z right now." Tell workers not to spawn their own subagents unless you want that.

**Measure before you design.** If the bug involves something external (a browser feature, a provider, a protocol), the first worker's job is ground truth: drive the real thing, log what it does, and leave behind a deterministic simulator. The simulator then powers the regression suite. Folklore has cost wrong first designs more than once.

**Every gate must be shown to fail.** A regression test ships with a negative control (disable the fix, the test goes red) and reports its sample size (routes visited, cases run). A sweep that visited zero pages passes vacuously.

**Reviewers get the code, not your conclusion.** Ask for defects, concrete scenarios and experiments, marked CONFIRMED or PLAUSIBLE. After you apply their findings, send the *same* reviewer the final files to re-run its checks. It takes minutes and catches what you broke while fixing.

**Prove the server you are testing is the build you just made.** A backgrounded server that cannot bind its port exits into a log nobody reads, and the previous build keeps answering; every experiment after that tests old code. After stopping a server, check the port is dead before starting the next one.

**Fix mechanical mistakes mechanically.** When a review shows a systematic error across many files, script the correction and reformat; do not re-delegate it.

**Split the release by risk.** A small critical fix and a wide low-risk pass are two tags. Ship the critical one as soon as it is verified. When the working tree holds both, cut the first release from a clean worktree:

```bash
W=<scratch>/release-wt
git -C <module> worktree add -b release/<name> "$W" origin/main
# copy ONLY the files of release 1 into "$W", then inside the worktree:
cd "$W"
git add -A && git commit -F <message-file>
git push origin release/<name>:main          # fast-forward only, never force
git tag -a vX.Y.Z -m "release vX.Y.Z" && git push origin vX.Y.Z
# bring the shared checkout's main to the released commit without touching its files:
git -C <module> fetch
git -C <module> status -sb                    # STOP if it is ahead of origin/main
git -C <module> reset origin/main             # mixed: moves main and the index, keeps the working tree
# after the last release:
git -C <module> worktree remove "$W" && git -C <module> branch -D release/<name>
```

Never chain `git commit --amend` after a commit that may have failed (for example on an `index.lock` collision with a build that calls git): it rewrites the previous, already-pushed commit. Check `git log -1` first.

**Run the module's real CI gate list before tagging**, not a subset: `pre-prod-check/ci-gates.sh` reads the list out of the CI file itself. A red verify job often leaves the deploy job *skipped*, which looks exactly like "waiting for a human".

**A tag is not a deploy, and a deploy is not a verification.** Watch the pipeline to the deploy button (`gitlab-deploy/pipeline-status.py <module> --wait`), play the deploy, then prove the new code is what is running: a marker the change adds, read from the live system and compared with a baseline you took BEFORE deploying. Then run the post-deploy smoke checks. If an image scan blocks the deploy, it is usually a new advisory against a dependency you did not touch: bump it in a clean worktree, re-run the gates, tag again.

## Writing a worker brief

A worker knows only what the brief says. Include, in this order:

1. **Role and stakes**: one line ("You are the REVIEWER for a change about to ship to every user").
2. **The problem and the hypothesis**, and what has already been ruled out.
3. **Facts already established** (measurements, file paths with line numbers). Paste them; do not make the worker rediscover them.
4. **Scope**: exact paths owned, paths forbidden, who else is working nearby.
5. **The shared-checkout rules** above, verbatim.
6. **Deliverable**: the exact shape of the final message (table of edits, ranked findings with reproduction, what was *not* covered). Ask for "what you could not verify" explicitly; workers otherwise report confidence, not coverage.

Launch independent workers in one message so they run concurrently. Verify that delegated work landed on disk.

## Report at the end

Lead with what shipped (module, tag, deployed or not, verified how), then what was found, what is still open, and anything ungated. Relay worker findings that matter; the user does not see worker reports.
