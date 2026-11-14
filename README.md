# claude-code-setup

This is the Claude Code configuration I use day to day: subagent roles, skills, hooks and a project-instructions template. It grew out of three real projects (a multi-service SaaS product, a Roblox game and a generative-media pipeline) and was cleaned of anything project-specific before publishing. Most of the rules here were added after something went wrong without them.

## The pipeline

Non-trivial work goes through an orchestrator (`/orchestrate`, or `/team-lead` when the task ends in a release). The main session plans and integrates; it does not write most of the code.

1. **Plan.** Split the task into the smallest pieces: one agent run, one disjoint set of files, one acceptance check each. Write the plan to a file.
2. **Implement in parallel.** `developer`, `designer` and `writer` agents each get a brief naming the files they may touch. They never commit, install packages or restart servers; the orchestrator owns shared resources.
3. **Review independently.** `tester` re-runs every gate itself and tries to break the change. `reviewer` gets the code, not the author's summary. For audits, `skeptic` agents try to refute each severe finding before anyone acts on it. Findings are marked confirmed or plausible.
4. **Gate.** Nothing merges on a red gate, and every new check has to fail on the broken code first, so it can't pass by accident. Two failed fix rounds on the same defect stop the loop and escalate to a stronger model for root cause.

Workers never ask me questions mid-task. They return `blocked: <decision>` and the orchestrator hands me one batched list at the end. Anything that costs real money or GPU time starts with a written run plan and a small pilot, has spending caps, and gets logged.

## Model routing

Each role pins a model in its frontmatter, by how expensive a mistake is:

| Model | Used for |
|---|---|
| Fable | architecture, hard decisions, analysis, prompts for paid generations, fix loops that failed twice |
| Opus | planning, orchestration, code review, testing, design and visual review, research |
| Sonnet | writing code |
| Haiku | running committed checks and other mechanical tasks, never writing code |

Exceptions go upward only. A role can run on a stronger model for a hard task, never a weaker one.

## Long autonomous sessions

Long sessions survive context compaction because state lives in files. `/precompact` collects facts with tools (git status per worktree, running agents, decisions with reasons, my corrections, next steps) into a `STATE.md`, then gives me the exact `/compact` line that makes the next context read it first.

`/night-shift` is for when I am away. A Fable agent plans parallel branches with caps and fallbacks, a heartbeat keeps the session awake, branches are checked by their output files, and when a branch hits a technical decision, a Fable agent makes the call instead of waiting for me. Anything that genuinely needs me goes into one morning question batch, with the default used in the meantime.

For stakeholders, `/analyst-report` packs a self-contained status report, and `/business-analyst-review` has a Fable analyst challenge it using only what an outside reader would get.

## Guard hooks

- `hooks/guard_protected.py` (PreToolUse) blocks deleting or moving files in protected directories, overwriting existing files where only new versions are allowed, editing frozen files such as model weights, and reading secret files into the conversation.
- `hooks/check_on_edit.py` (PostToolUse) runs a project checker, for example a banned-words list for user-facing copy, on every file written under configured directories, and sends the hits back so they are fixed before anyone sees them.

Both are configured with a small JSON file and fail open. They catch mistakes; they are not a security boundary. `settings.example.json` shows the wiring plus deny rules for force-push and `.env` reads.

## What is here

```
agents/      14 role definitions (architect, researcher, developer, fixer, designer,
             reviewer, tester, analyst, business-analyst, prompt-writer,
             visual-reviewer, skeptic, runner, writer)
skills/      14 skills: orchestrate, team-lead, night-shift, precompact,
             pre-prod-check, full-audit, frontend-visual-audit, release-tag,
             commit-push, update-docs, gitlab-deploy, compliance-review,
             analyst-report, business-analyst-review
hooks/       guard_protected.py, check_on_edit.py + example configs
templates/   CLAUDE.md skeleton for a new project
examples/    how the setup was used on the three projects
```

## Install

User-wide, for every project:

```bash
cp -r agents skills ~/.claude/
```

Per project (overrides user-level definitions with the same name):

```bash
mkdir -p .claude/hooks
cp -r agents skills .claude/
cp hooks/*.py .claude/hooks/
cp hooks/guard.example.json .claude/hooks/guard.json
cp templates/CLAUDE.md ./CLAUDE.md
```

Then merge `settings.example.json` into `.claude/settings.json`, edit `guard.json`, and fill in `CLAUDE.md`. The scripted skills read their project specifics from config files or environment variables (`pre-prod.conf`, `audit.config.json`, `GITLAB_*`); each `SKILL.md` lists what it needs. Hooks need Python 3; scripts need bash (Git Bash works on Windows).

Restart Claude Code after changing agent definitions; they load at session start.

## License

MIT.
