---
name: analyst-report
description: Write a self-contained status report for a business analyst / product manager who has no repo access - everything since the previous report, every number traced to a file, owner tasks marked done only with evidence, explicit answers to the analyst's last checklist - then pack the report and every text file it references into one zip with a packer that refuses secrets, media and blocked folders. Use when the owner asks for a status report or a summary for the analyst / PM / stakeholders.
argument-hint: [optional: period or focus; paste the analyst's last reply here]
---

You are the orchestrator writing a status report for the business analyst. Extra input: $ARGUMENTS

**The reader has no repo or git access.** The report must stand on its own, and every file it mentions is attached. A repo path is never the only pointer to a fact.

## 0. Rules

- Facts and numbers **only from repo sources** (file, commit, log); every estimate marked `~`.
- Absolute dates in the owner's timezone (convert machine-local times from git and logs). Never "yesterday" or "today".
- Owner tasks (accounts, verification, approvals, selections) are **done only with evidence**: a decisions-log row, a commit, a file, a message from the owner. Otherwise write "not done" or "no data".
- No new user-facing copy; quote only what is already approved.
- No secrets: never read or quote `.env`, tokens or credentialed URLs. No media: do not open images or video; counts and file names only.
- Attachments are text only (the report plus referenced md/csv/yaml/json/txt/source). Never media, datasets, outputs, archives, model files or secret files. Media the owner already received is mentioned by name as "sent to owner earlier", not attached.

## 1. Plan the period

1. Previous report = the newest `work/*_status/summary_*.md`. Period = its end time until now.
2. The analyst's last reply (pasted by the owner, in `$ARGUMENTS`, or produced by `/business-analyst-review`): extract its **"What I expect in the next report"** list verbatim. Each item gets an explicit answer in section 4. No reply available -> section 4 answers the previous report's open decisions and plan, and says so.
3. Folder `work/<YYYY-MM-DD>_status/`, file `summary_<dd_mm_hhmm>.md`, files list `summary_<dd_mm_hhmm>_files.txt` next to it.

## 2. Gather sources (tick every line)

- [ ] decisions log: **every row dated inside the period** (count them; section 1 must cover all)
- [ ] backlog: new or changed rows
- [ ] model / artifact registries the project keeps: new versions and their eval numbers
- [ ] spec/canon changelogs: changes in the period
- [ ] worker reports in the period (head and summary of each)
- [ ] `git log --all --since="<period start>" --date=iso --pretty="%h %ad %s"`
- [ ] job queues and outputs created in the period: count files and QC statuses (counting is fine; opening media is not)
- [ ] automated gate results: numbers from their reports
- [ ] compute time: from reports and logs; `~` when estimated
- [ ] spend: the spend ledger, provider dashboards via CLI only if a key is in the environment; no data -> "$0 / no data", never a guess
- [ ] the previous report's open decisions: which got answered and which are still open

Drafting can be delegated to the `writer` agent (pass this checklist, the period, the analyst's list and source **paths**, never secret values). You still do step 4 yourself.

## 3. Mandatory sections, in this order

```
# Status report: <period start -> end, tz>
_Self-contained; every file mentioned is in <zip name> (paths inside = repo paths). Previous report: <name>. Facts; estimates ~._
## 0. Status in one line
## 1. Owner decisions in the period (grouped by work line)
## 2. Done per work line
## 3. Key numbers (metric | value | source file)
## 4. Answers to "What I expect in the next report" (each item: done / partly / NOT done + why + ~date)
   Owner tasks on the critical path get their own honest lines.
## 5. Risks (risk -> impact -> what we do)
## 6. Open decisions for the owner: ONE list
## 7. Budget (spent this period / total, approved caps, expected lines ~)
## 8. Attached files (= zip contents, one line each)
```

Two to three screens. Cite the source file in brackets after every number.

## 4. Verify before packing

- Every number in sections 2, 3 and 7 traces to a file or commit you read in step 2; fix it or mark it `~`.
- Decisions-log rows in the period: the count in section 1 equals the count in the file.
- Every item of the analyst's list has a line in section 4.
- Every path mentioned in the report is in `_files.txt`, and every line of `_files.txt` appears in section 8.
- Run the project's content checker on the report if it quotes prompts or copy.

## 5. Pack and deliver

1. `_files.txt`: the report first, then each referenced text file, one repo-relative path per line (`#` comments allowed; a folder entry adds its text files).
2. Dry run, then for real:
   ```bash
   python .claude/skills/analyst-report/pack_report.py work/<date>_status/summary_<dd_mm_hhmm>_files.txt <out-dir>/analyst_<dd_mm_hhmm>.zip --dry-run
   python .claude/skills/analyst-report/pack_report.py work/<date>_status/summary_<dd_mm_hhmm>_files.txt <out-dir>/analyst_<dd_mm_hhmm>.zip
   ```
   The packer refuses secret files, blocked folders, media and binaries, and any file containing a token-like string (it prints file and line, never the token). On REFUSED: drop, replace or redact the file. Never bypass it. Keep the zip out of git.
3. Commit the report and `_files.txt` if the project allows it.
4. Hand the zip and the report to the owner (send it if your client supports sending files), or run `/business-analyst-review` on it directly.
5. One screen in chat: status line, top 3 numbers, what is NOT done, the open-decisions list, the zip name.

Configure the packer per project with env vars: `PACK_ROOT` (default: repo root), `PACK_BLOCKED_DIRS` (space-separated top-level folders to refuse, added to the defaults), `PACK_SECRET_VARS` (extra variable names whose assignments count as secrets).
