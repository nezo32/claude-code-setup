---
name: gitlab-deploy
description: Watch a module's GitLab tag pipeline until it is deployable, play the manual deploy job through the API for one, several or all modules, and wait for the deploy and post-deploy smoke job. Playing a production deploy job rolls PRODUCTION - when the user asked for a deploy that is the authorization; otherwise confirm the tag first. Use when asked to "deploy <module>", "roll it out", "trigger the deploy job", or "deploy the latest tag".
---

# GitLab deploy

Release model this skill assumes: a pushed tag starts a pipeline `verify -> build -> scan -> deploy:<env> (manual) -> rollback (manual)`. Pushing the tag only *builds*; the deploy jobs are manual. This skill plays them through the GitLab API instead of the UI, and tells you why a deploy button is not there yet.

> **Playing `deploy:prod` rolls production.**
> If the user asked for a deploy ("deploy X", "roll it out", "release to prod"), that is the authorization: run `--dry-run` first to resolve the pipeline and tag, then run for real and report the exact modules, environment and tag.
> If they did not ("ship it", "cut a release", "commit and push" mean land and tag), confirm the modules, environment and tag first.
> Either way, say plainly if the release is ungated (pre-prod checks not run, e2e not executed). That is information for the operator, not a reason to block a deploy they asked for.

## Setup

Copy `.env.example` to `.env` next to the scripts (it is gitignored) or export the variables:

| Var | Meaning |
|---|---|
| `GITLAB_URL` | your GitLab base URL |
| `GITLAB_TOKEN` | personal access token, `api` scope |
| `GITLAB_PROJECTS` | `module=group/project` pairs, comma-separated |
| `GITLAB_BUILD_ONLY` | modules whose pipelines have no deploy job (skipped cleanly) |
| `GITLAB_ALL_ORDER` | deploy order for `all` (e.g. backend before frontend) |

Never commit `.env`: it holds a production deploy credential. Never print the token.

## 1. Watch the pipeline first

A red verify or scan job turns the manual deploy job `skipped`, which in the UI looks the same as a button waiting to be pressed. Run this in the background after tagging:

```bash
python .claude/skills/gitlab-deploy/pipeline-status.py web --wait                    # until DEPLOYABLE or BLOCKED
python .claude/skills/gitlab-deploy/pipeline-status.py web --trace scan:image        # tail the failing job
python .claude/skills/gitlab-deploy/pipeline-status.py web --wait --until deployed   # after playing: deploy + smoke
```

Exit 0 = state reached, 1 = a blocking job failed, 3 = timed out. If an image scan blocks, it is usually an advisory published since the last release against a dependency you did not touch: bump it in a clean worktree, re-run the gates, tag again.

## 2. Play the deploy

```bash
python .claude/skills/gitlab-deploy/trigger-deploy.py all --dry-run     # resolve, play nothing
python .claude/skills/gitlab-deploy/trigger-deploy.py web               # latest tag, prod
python .claude/skills/gitlab-deploy/trigger-deploy.py web api           # several
python .claude/skills/gitlab-deploy/trigger-deploy.py web --env staging
python .claude/skills/gitlab-deploy/trigger-deploy.py web --tag v1.4.0
python .claude/skills/gitlab-deploy/trigger-deploy.py web --force       # re-run one that already ran
```

Per module: resolve the tag (given or latest by version), find that tag's latest pipeline, pick `deploy:<env>` (or exactly one `deploy:<env>:<variant>`, or a plain `deploy`), play it if it is manual, otherwise report its status and skip. With `--force` a finished job is retried and played. If the requested environment's job does not exist, that is an error listing what does exist: the script never plays the wrong environment. One module failing does not stop the rest.

## 3. Prove it

A green deploy job is not proof. After `DEPLOYED`, show that the running system carries the change: a marker the release adds, read from the live system and compared with a baseline taken before the deploy. Then run the post-deploy smoke checks.

## Notes

- Deploy needs a green build. Playing deploy while the build is still running may fail on the dependency; `--dry-run` shows the job status.
- This skill does not cut tags (`release-tag` does) and does not roll back (play the rollback job from the last known-good tag's pipeline).
- Stdlib-only Python; use whichever `python` on your PATH is real.
