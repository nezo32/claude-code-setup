---
name: compliance-review
description: Run the project's content-compliance gate on a file or folder before it is published or shipped - non-negotiable rules, platform rules, disclosure requirements and a banned-words checker - and return SHIP / FIX / BLOCK. Delegates to the reviewer agent so the check is independent of whoever wrote the content. Use before publishing any user-facing text, prompt set, campaign calendar, dataset or generated media batch.
argument-hint: <path> [target: e.g. web|social|email|internal]
---

Review target: $ARGUMENTS

This is a pattern for any project that publishes generated content (copy, prompts, images, video, datasets) under rules that must never be broken: legal and platform rules, disclosure labels, brand and IP restrictions, audience restrictions, licence restrictions on the models used.

## Prerequisites in the project

- A **non-negotiables list** in `CLAUDE.md` (or a doc it points to), numbered, each one checkable.
- A **pre-publication checklist** per target surface.
- A **banned-words / pattern checker** script that exits 1 on hits, with a profile per target surface (stricter for public surfaces). Wire it into the `check_on_edit.py` hook as well so hits are caught at write time.
- An **escalation list**: decisions only the owner can make.

## Procedure

Delegate to the `reviewer` subagent (Agent tool, `subagent_type: reviewer`) with:

- the target path(s) and target surface(s). If not given, infer from the file (public copy -> the strictest public profile; prompts and dataset captions -> the prompt profile; internal docs -> internal).
- the instruction to write `<work-dir>/<YYYY-MM-DD>_compliance_<slug>/review.md`
- this checklist:
  1. Go through every non-negotiable **line by line**: PASS / FAIL / N/A with evidence (`file:line`).
  2. Go through the pre-publication checklist items that apply to this deliverable type.
  3. Run the checker for each target surface, and the prompt profile over generation prompts and captions. Paste the hit lines.
  4. Grep content, prompts, file names and configs for: real-person names or "looks like" references; models or assets whose licence forbids this use; restricted content routed to a surface that does not allow it; missing disclosure labels in the publishing plan; claims the product must not make (health, financial, legal).
  5. Check that anything on the escalation list was escalated, not decided.

For a quick check you can also run the checker directly on the path.

## Verdict

- **SHIP**: all clear.
- **FIX**: numbered list, each with item, `file:line`, what to change, and which role makes the change.
- **BLOCK**: any breach of a non-negotiable marked as blocking, or an unescalated owner decision. One blocking breach blocks the whole deliverable.

Relay the verdict to the user. Do not edit the reviewed files as part of this skill.
