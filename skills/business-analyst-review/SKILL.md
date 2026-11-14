---
name: business-analyst-review
description: Run the business-analyst agent (on the strongest model) over the newest status report from /analyst-report, with the same information boundary an external analyst would have (the report plus its packed files list), save its reply next to the report, verify it, and show the owner a one-screen summary. Decisions are logged only after the owner accepts them. Use when the owner asks for the analyst's / PM's take on a status report, or right after /analyst-report.
argument-hint: [optional: path to work/<date>_status/summary_<dd_mm_hhmm>.md | a focus question for the analyst]
---

You are the orchestrator launching the business analyst over a status report. Input: $ARGUMENTS

This replaces only the step of forwarding the report to an outside analyst and pasting the reply back. The report is still produced by `/analyst-report`, and the owner still decides.

## 0. Rules

- **Never draft the report here.** No report -> stop and tell the caller to run `/analyst-report` first.
- The analyst sees only what an outside analyst would see: the report, the files in its `_files.txt`, its own previous reply. Pass **paths**, never pasted contents, never secret values.
- No media is opened, by you or by the analyst. This skill edits nothing except the one reply file.
- The analyst **recommends**; the owner decides. Nothing from the reply enters the decisions log until the owner accepts it (step 6).

## 1. Find the report

1. A path ending in `summary_<dd_mm_hhmm>.md` in `$ARGUMENTS` -> use it. Otherwise the newest `work/*_status/summary_*.md` (by date and time in the name, mtime as tiebreak).
2. Its `summary_<dd_mm_hhmm>_files.txt` must exist next to it. Missing -> **stop**: "no files list, run /analyst-report first". Do not build a list yourself.
3. Boundary check with the packer (writes nothing): `python .claude/skills/analyst-report/pack_report.py <files.txt> <scratch>/_check.zip --dry-run`. REFUSED -> stop and report the lines; the report gets fixed through `/analyst-report`, never by trimming the list here.
4. Previous reply for continuity: the newest `business_analyst_feedback_*.md` older than this report, if any. Owner focus text from `$ARGUMENTS` goes into the brief verbatim.

## 2. Output path (never overwrites)

The report's folder, name `business_analyst_feedback_<dd_mm_hhmm>.md` with the current time. If it exists, add `_v2`, `_v3`. Check before launching and give the analyst the final path.

## 3. Launch the analyst

Agent tool, `subagent_type: business-analyst`, `model: fable` (set both explicitly; the model is the point of this skill). One agent, no parallel copies. Brief, paths only:

```
Re-read your definition .claude/agents/business-analyst.md first (agent files are cached at session start).
Report: <path to summary_*.md>
Files list (your whole world besides the report): <path to _files.txt>
Previous reply: <path | none>
Now: <date time tz>
Owner's focus: <text | none>
Write exactly one file: <output path>. Skeleton and rules are in your definition. Reply with the path, the section 0
line, the top 3 recommendations, and blocked: items. Never ask the owner.
```

## 4. Verify the reply before showing anything

- The file exists, is non-empty and has the sections "Status in one line", "Critical path", "Money", "What I expect in the next report". A missing section -> send the agent back once with the gap; still missing -> report it as partial, do not fill it in yourself.
- No secrets: grep the reply for token prefixes and `Authorization:`. A hit -> delete the file and report the line number only.
- Run the project's content checker if the reply quotes prompts or copy.
- Any "approved" on an owner-decision item -> present it as "recommendation, owner's decision" (and fix the agent file; it is told not to write that).
- Commit the reply if the project allows it.

## 5. Show the owner: one screen

1. File path (and the report it answers).
2. The analyst's section 0, verbatim.
3. Critical path rows with their status.
4. Top 3 to 5 recommendations, one line each, marked "owner's decision" where applicable.
5. Money: actual vs. recommended cap.
6. "What I expect in the next report": number of items and the control dates.
7. The question: **which recommendations do you accept / reject / defer** (by number).

## 6. Logging: only after the owner answers

- One decisions-log row per item the owner explicitly accepts: date, "business analyst (accepted by owner)", the recommendation in short, the reply file and section, what changes.
- Rejected items: one row "business analyst (rejected by owner)" with the reason if given. Deferred items: nothing logged; they stay in the reply's checklist.
- Never log the whole reply and never log before the owner answers.
- The next `/analyst-report` takes this reply's "What I expect in the next report" list as its section 4 checklist.
