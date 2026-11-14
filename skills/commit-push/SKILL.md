---
name: commit-push
description: Commit and push every git submodule first, then the root repo, staging in the root only the submodule pointers that moved plus paths you name. Use when asked to "commit and push", "push all submodules", or to land changes across a superrepo of submodules. Works on a plain repo too (it just handles the root).
---

# Commit and push: submodules first, then root

In a superrepo, the root only stores a **pointer** (a commit SHA) to each submodule. **The order is the whole point:** push each dirty submodule first, *then* commit and push the root. The root commit records the new pointers, and those commits must already exist on the submodule remotes, or a fresh `git clone --recurse-submodules` cannot resolve them.

The driver is `.claude/skills/commit-push/commit-push.sh`. It auto-discovers submodules from `.gitmodules`, so a newly added submodule is never missed.

## Run

**1. Preview first** (no writes):

```bash
bash .claude/skills/commit-push/commit-push.sh
```

For each module, and the root last, it reports `skip` (clean), `would push` (committed but unpushed), or `would commit/push` (dirty, with the file list).

**2. Commit and push everything with one message:**

```bash
bash .claude/skills/commit-push/commit-push.sh -m "feat: short description"
```

Each dirty submodule gets `git add -A`, a commit with your message plus the attribution trailer, and a push. Clean modules are skipped.

**The root is handled narrowly, on purpose.** It stages only the submodule pointers that moved, plus any root path you name:

```bash
bash .claude/skills/commit-push/commit-push.sh -m "docs: ..." -p CLAUDE.md -p e2e/foo.spec.ts
```

Everything else modified or untracked in the root is **left alone and listed**. A root tree is often shared between sessions and tools; a whole-tree `git add -A` there once committed other people's parked work under one message. `--root-all` restores whole-tree staging for a checkout you own alone. Always read the dry run first.

Set `COMMIT_TRAILER` to the attribution line(s) your session should use; the default is a generic `Co-Authored-By: Claude` line (the script does not hard-code a model name, which goes stale).

## Tailored per-module messages

One message across unrelated submodules is often wrong. Commit the submodules by hand, then let the driver push them and handle the root:

```bash
git -C service-a add -A && git -C service-a commit -m "feat(api): ..."
git -C service-b add -A && git -C service-b commit -m "fix(worker): ..."
bash .claude/skills/commit-push/commit-push.sh -m "chore: bump service-a + service-b"
```

A manually committed submodule is *clean but ahead*, so the driver pushes it without re-committing.

## Gotchas

- **Detached HEAD in a submodule**: the driver refuses (a commit there is orphaned). `git -C <module> checkout main`, then re-run.
- **Root must be last.** Pushing the root before its submodules leaves dangling pointers. The driver enforces the order.
- **Secrets never get committed.** Real env files must be git-ignored so `git add -A` cannot stage them; only `*.example` templates are tracked. If a secret value changed, rotate it; never commit it.
- Windows line-ending warnings from `git add` are noise, not errors.

## Verify

```bash
for m in $(git config -f .gitmodules --get-regexp '^submodule\..*\.path$' | awk '{print $2}') .; do
  echo "=== $m ==="; git -C "$m" status -sb | head -1
done
```

The list is read from `.gitmodules`, never typed out, so it cannot silently omit a module. Every line should read `## main...origin/main` with no `[ahead N]` and no dirty files.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `DETACHED HEAD` | `git -C <module> checkout main`, re-run |
| `push failed` (non-fast-forward) | `git -C <module> pull --rebase`, re-run |
| dangling submodule pointer on clone | the root was pushed before the submodule; push the submodule |
| `-m requires a non-empty commit message` | pass `-m "..."`; a bare call is dry-run only |
