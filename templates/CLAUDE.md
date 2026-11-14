# CLAUDE.md: <project name>

<!--
Template distilled from the project instructions I use on a SaaS product, a game and a
generative-media pipeline. Delete what does not apply; keep sections short. Everything
here overrides default agent behaviour, so write rules you actually want enforced.
-->

<One paragraph: what this is, who it is for, the stack in one line.>
Source of truth: `docs/SPEC.md`. Decisions: `docs/DECISIONS.md`. Plan: `docs/PLAN.md`.
Status and resume point: `docs/STATUS.md`. Current state (stack in use, references, quality gates, closed lines): `docs/STATE.md`; read it before planning.
Trade-offs, in order: 1) <e.g. correctness and data safety>, 2) <simplicity>, 3) <polish>.

## Source-of-truth precedence

When documents disagree, the higher one wins. Never average them; fix the lower one.

1. Non-negotiables (below)
2. `docs/SPEC.md`
3. `docs/DECISIONS.md` (newest row wins; a change is a new row naming the row it overrides)
4. Everything else (research reports are dated snapshots, not instructions)

## Non-negotiables

Numbered, each checkable by a reviewer. A task that conflicts with one: stop and report the conflict; do not execute.

1. <e.g. the server is authoritative for money, ownership and saves>
2. <e.g. no secrets in git, logs, prompts or agent briefs>
3. <e.g. legal / platform / disclosure rule>

## Verify

- **`<gate command>` must exit 0 before work is done.** Per-run variant when several agents run: `<gate command> --run <task-id>`.
- New backend behaviour gets an end-to-end test that drives it the way a real client does.
- UI changes are verified in a running app at a phone and a desktop viewport, in every supported locale. Verify with text (accessibility snapshot, evaluated layout facts such as overflow and bounding boxes), not screenshots, unless the task is explicitly visual.
- Image policy: <none for anyone | design roles may capture to files and open them>.
- Current facts about external APIs and platforms are checked in docs, not recalled. Note the date of what you cite.

## Paid and compute-heavy work (generative / ML projects)

- Above <$X or N GPU-minutes> per run: recipe card (`00_recipe.md`: hypothesis, one variable, pilot, numeric gates, cap, stop rule) and a pilot first; scale after the owner's yes.
- Caps per run and per task; a cap is raised only by a written reason in the recipe. At most two paid runs per hypothesis.
- Every spend -> `work/SPEND.csv` at run time; every owner verdict on an output -> `work/VERDICTS.csv` (tag + quote).
- Prompts for paid calls come from the `prompt-writer` agent and `docs/PROMPT_RULES_v*.md`, never by hand.
- The owner sees only outputs that passed the hard gates in `docs/STATE.md` "Gates" (the only place thresholds live). Fails -> reject folder + a numbered line, no auto-retry; borderline -> to the owner with the number.
- Results go out in packages: one per stage, at most two files per item, three lines on what to judge.
- At most two paid fix passes per item; a third complaint of the same class -> respecify.
- Repeatable steps live in `tools/` with tests; a one-off script needed twice moves there.
- Compute (local GPU, long jobs) only on <the owner's go-ahead | a standing rule>.

## Code rules

- <strictness: types on, `any` only with a justifying comment>
- <numbers and tunables only in config modules>
- <one registry for routes/messages; payload types in one place>
- Validate every external input (type, range, ownership); rate-limit; log rejections.
- Pure logic in side-effect-free modules with unit tests.
- Migrations are additive and backward-compatible; never ship a drop/rename in the same release as the code that needs it.
- Match the surrounding style; comments only where the code is not obvious.
- Canonical inputs (spec/prompt blocks, reference files) are used only in the versions listed here as in force: <list>. Code loads them through one constant.
- Deliverables carry a version suffix (`_v1`, `_v1.1`); a shipped version is never overwritten, it is bumped.

## Orchestration

- Roles live in `.claude/agents/`. A role not registered in the session -> `general-purpose` whose first line is `Read .claude/agents/<role>.md and follow it.`
- Non-trivial tasks run through `/orchestrate` (or `/team-lead` for ship-and-deploy work). Trivial ones (a typo, one lookup) inline.
- **Model routing** (role frontmatter; ad-hoc launches follow it too): Fable for the hardest and most expensive work (architecture, hard decisions, analysis, a fix loop that failed twice); Opus for planning, orchestration, review, testing and design; Sonnet for writing code; Haiku for simple mechanical tasks, never code. Exceptions only upward.
- Split work into the smallest tasks: one run, one disjoint file set, one acceptance check. Briefs name the files a worker may edit.
- Workers talk only to the orchestrator, through files: reports to `docs/reports/`, research to `docs/research/`, final message 12 lines or fewer. They never ask the owner; they return `blocked: <decision>`, and the orchestrator batches all open decisions into one list.
- The orchestrator owns shared resources: package installs, dev servers, containers, the browser, git. Workers never commit.
- **User-visible work** goes only to `designer`, never `developer`/`fixer`. Order: direction (mockup, no code) -> owner -> build against the approved reference -> owner. The owner approves design; visual review is advisory.
- **Review is independent**: reviewers get the code, not the author's conclusion, and run the gates themselves.
- **Fix loops**: two failed rounds of one defect -> stop; a Fable run finds the root cause and picks the approach.
- Owner questions are batched, recommended option first. Owner away -> record in `docs/STATUS.md` "Waiting for the owner" and keep working around it.
- Big tasks get a plan dir under `.plan/<task>/` (git-ignored).
- Before a pause or `/compact`: run `/precompact`. Owner away overnight: `/night-shift <goals; permissions>`.
- Status for stakeholders: `/analyst-report`, then `/business-analyst-review`; analyst recommendations enter `docs/DECISIONS.md` only after the owner accepts them.

## Git and release

- Base branch `<main>`; work on branches. Routine commits, pushes and merges are <pre-authorized | only on request>; force-push, history rewrites and deleting remote branches always need confirmation.
- In a shared checkout, stage only your own paths; never `git add -A` at the root.
- Release = pushed semver tag (`/release-tag`). Run the module's full CI gate list before tagging, not a subset.
- A tag is not a deploy, and a deploy is not a verification. Production deploys only on an explicit instruction; after deploying, prove the new code is what runs.

## Secrets

Live in `<.env | vault>`, git-ignored, template in `.env.example`. Load them through the environment. Never print, log, commit, or paste values into files, prompts or agent briefs.

## Guardrails wired into `.claude/`

- `hooks/guard_protected.py` (PreToolUse): blocks delete/move in `<protected dirs>`, overwriting existing files in `<no-overwrite dirs>`, and reading secret files into the conversation.
- `hooks/check_on_edit.py` (PostToolUse): runs `<checker>` on files written under `<dirs>` and feeds hits back.

## Repository layout

```
<dir>/   <one line each>
```

## Environment notes

<Machine-specific traps: which python is real, missing tools, ports owned by other programs.>
