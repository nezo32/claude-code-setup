---
name: release-tag
description: Cut a release by bumping the latest semver git tag and pushing it, which triggers the repo's tag pipeline. Refuses a dirty, off-main or unpushed tree. Works per repo, per submodule, or across every module with unreleased commits (--all). Defaults to a patch bump. Use when asked to "release", "cut a release", "tag a new version", "bump the version", or "release everything that changed".
---

# Release tag

In this setup a module is released by **pushing a git tag**; that starts its CI pipeline (typically build -> scan -> manual deploy -> manual rollback). This skill computes the **next** semver tag from the latest one and pushes it, with guardrails so you never tag a dirty or stale tree.

## Run

```bash
# one repo (current dir or a submodule by name), on main:
bash .claude/skills/release-tag/bump-tag.sh                 # patch bump (default)
bash .claude/skills/release-tag/bump-tag.sh minor
bash .claude/skills/release-tag/bump-tag.sh service-a major

# every module with commits since its last tag:
bash .claude/skills/release-tag/bump-tag.sh --all
bash .claude/skills/release-tag/bump-tag.sh --all minor

# preview only:
DRY_RUN=1 bash .claude/skills/release-tag/bump-tag.sh --all
```

`--all` iterates `$RELEASE_MODULES` (space-separated) or, if unset, every submodule in `.gitmodules`. Set `RELEASE_BRANCH` if your release branch is not `main`.

## What it does

1. Resolves the target repo (`.` or a submodule dir under the root).
2. **Refuses unless safe**: on the release branch, clean working tree, level with `origin/<branch>` (a tag must point at what is actually pushed).
3. Finds the latest `vMAJOR.MINOR.PATCH` tag (version sort), bumps the requested part (`minor`/`major` reset the lower parts), keeps the `v` prefix style. No tags yet -> `v0.1.0`.
4. Skips when there are no commits since the last tag; fails if the computed tag already exists.
5. Creates an **annotated** tag and pushes only that tag.

In `--all` mode a module is **skipped** (not failed) when it is off-branch, dirty, not level with the remote, or unchanged. It prints one line per module and a `tagged / skipped / error` summary. Idempotent: re-running tags nothing new.

## Notes

- Pushing the tag only starts the pipeline. If deploy is a manual job, this skill does not deploy; use `gitlab-deploy` (or your CI's equivalent) once the pipeline reaches the deploy button.
- Run `pre-prod-check` and the module's full CI gate list **before** cutting the tag. The tag is the release, not a test run.
- When the tree mixes a release with unfinished work, cut the release from a clean `git worktree` (see the `team-lead` skill); this script correctly refuses a dirty tree.
- To redo a tag: `git push --delete origin <tag>` and re-run, or bump again.
