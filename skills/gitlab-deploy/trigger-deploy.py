#!/usr/bin/env python
"""Play the manual `deploy:<env>` job on a module's tag pipeline in GitLab.

Release model this assumes: pushing a git tag starts a pipeline like
    verify -> build (auto) -> scan (auto) -> deploy:<env> (MANUAL) -> rollback (MANUAL)
This script finds the latest tag pipeline for one, several or all modules and
plays its manual deploy job through the API. Stdlib only. Configuration is in
the environment; see _gitlab.py.

Usage:
    python trigger-deploy.py web
    python trigger-deploy.py web api
    python trigger-deploy.py all --dry-run
    python trigger-deploy.py web --env staging
    python trigger-deploy.py web --tag v1.4.0
    python trigger-deploy.py web --force          # re-run a deploy that already ran
"""
import argparse
import sys

from _gitlab import all_order, api, build_only, die, pid, projects, token

PLAYABLE = {"manual", "created", "scheduled"}


def latest_tag(tok, project):
    tags = api(tok, "GET", f"/projects/{pid(project)}/repository/tags",
               query={"order_by": "version", "sort": "desc", "per_page": 1})
    return tags[0]["name"] if tags else None


def latest_pipeline(tok, project, ref):
    pipes = api(tok, "GET", f"/projects/{pid(project)}/pipelines",
                query={"ref": ref, "order_by": "id", "sort": "desc", "per_page": 1})
    return pipes[0] if pipes else None


def deploy_jobs(tok, project, pipeline_id):
    jobs = api(tok, "GET", f"/projects/{pid(project)}/pipelines/{pipeline_id}/jobs",
               query={"per_page": 100})
    return [j for j in (jobs or []) if j["name"] == "deploy" or j["name"].startswith("deploy:")]


def pick_deploy_job(jobs, env):
    """`deploy:<env>`, else exactly one `deploy:<env>:<variant>`, else plain `deploy`.

    A module that rolls out some other way than a Deployment (for example by
    patching an image reference in a ConfigMap) may name its job
    `deploy:<env>:<variant>`; matching only the exact name would silently report
    "no deploy job" for a module that has one. More than one variant is ambiguous
    and refused rather than guessed.
    """
    by_name = {j["name"]: j for j in jobs}
    if f"deploy:{env}" in by_name:
        return by_name[f"deploy:{env}"]
    variants = sorted(n for n in by_name if n.startswith(f"deploy:{env}:"))
    if len(variants) == 1:
        return by_name[variants[0]]
    if len(variants) > 1:
        raise ValueError(f"multiple deploy jobs for env {env!r}: {', '.join(variants)}")
    return by_name.get("deploy")


def handle(tok, module, project, env, tag_override, force, dry_run):
    if module in build_only():
        return True, "skip - build-only module, no deploy job"
    tag = tag_override or latest_tag(tok, project)
    if not tag:
        return False, "no tags found"
    pipe = latest_pipeline(tok, project, tag)
    if not pipe:
        return False, f"no pipeline for tag {tag}"
    pipe_url = pipe.get("web_url", "")

    jobs = deploy_jobs(tok, project, pipe["id"])
    if not jobs:
        return True, f"skip - tag {tag}: no deploy job in pipeline ({pipe_url})"
    job = pick_deploy_job(jobs, env)
    if not job:
        avail = ", ".join(sorted(j["name"] for j in jobs))
        # Never silently play the wrong environment.
        return False, f"tag {tag}: no `deploy:{env}` job (available: {avail}) ({pipe_url})"

    st = job["status"]
    label = f"tag {tag} -> {job['name']} #{job['id']} [{st}] {job.get('web_url', '')}"
    if dry_run:
        would = "PLAY" if st in PLAYABLE else ("RETRY (force)" if force else "SKIP")
        return True, f"[dry-run] would {would}: {label}"
    if st in PLAYABLE:
        res = api(tok, "POST", f"/projects/{pid(project)}/jobs/{job['id']}/play")
        return True, f"played {job['name']} for {tag}: {res.get('web_url', label)}"
    if force:
        res = api(tok, "POST", f"/projects/{pid(project)}/jobs/{job['id']}/retry")
        if res and res.get("status") in PLAYABLE:
            res = api(tok, "POST", f"/projects/{pid(project)}/jobs/{res['id']}/play")
        return True, f"retried+played {job['name']} for {tag}: {res.get('web_url', label)}"
    return False, f"deploy already '{st}' for {tag} - use --force to re-run ({job.get('web_url', '')})"


def main():
    mods = projects()
    ap = argparse.ArgumentParser(description="Play the manual deploy job on a module's tag pipeline")
    ap.add_argument("modules", nargs="+", help=f"module name(s) ({', '.join(mods)}) or `all`")
    ap.add_argument("--env", default="prod", help="environment suffix of the job (default: prod)")
    ap.add_argument("--tag", help="deploy this tag instead of each module's latest")
    ap.add_argument("--token", help="GitLab token (else $GITLAB_TOKEN / .env)")
    ap.add_argument("--force", action="store_true", help="re-run a deploy that already ran")
    ap.add_argument("--dry-run", action="store_true", help="resolve and print the plan; play nothing")
    args = ap.parse_args()
    tok = token(args.token)

    req = [m.lower() for m in args.modules]
    if "all" in req:
        targets = all_order()
    else:
        targets = []
        for m in req:
            if m not in mods:
                die(f"unknown module '{m}' (valid: {', '.join(mods)}, all)")
            if m not in targets:
                targets.append(m)
    if args.tag and len(targets) > 1:
        print(f"note: --tag {args.tag} applied to every target module", file=sys.stderr)

    ok = err = 0
    for m in targets:
        try:
            success, msg = handle(tok, m, mods[m], args.env, args.tag, args.force, args.dry_run)
        except (RuntimeError, ValueError) as e:
            success, msg = False, str(e)
        print(f"{'OK ' if success else 'ERR'} {m:12} {msg}")
        ok, err = (ok + 1, err) if success else (ok, err + 1)

    print(f"\n-- {ok} ok, {err} error(s) --")
    sys.exit(1 if err else 0)


if __name__ == "__main__":
    main()
