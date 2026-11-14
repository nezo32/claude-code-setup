#!/usr/bin/env python
"""Show, or wait for, a module's tag pipeline: can I deploy yet, and if not, why?

A pushed tag only STARTS the pipeline. Between the tag and a playable deploy job
sit verify, build and scan jobs, and when one of them fails the manual deploy job
turns `skipped`, which in the UI looks exactly like a job waiting to be played.

    python pipeline-status.py web                          # latest tag, one shot
    python pipeline-status.py web --tag v1.4.2
    python pipeline-status.py web --wait                   # block until DEPLOYABLE or BLOCKED
    python pipeline-status.py web --wait --until deployed  # ... until deploy + smoke finish
    python pipeline-status.py web --trace scan:image       # tail a job's log

Exit: 0 = state reached (or one-shot printed), 1 = a blocking job failed,
2 = usage/API error, 3 = timed out.

Jobs with `allow_failure` never count as a failure (advisory by the pipeline's own
definition) but are still printed: read them. An advisory scanner often lists the
vulnerability that a blocking image scan will gate on in the next release.

Read-only: plays nothing. Stdlib only. Config: see _gitlab.py.
"""
import argparse
import json
import sys
import time

from _gitlab import api, gitlab_url, pid, projects, token

BAD = {"failed", "canceled"}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("module")
    ap.add_argument("--tag")
    ap.add_argument("--token")
    ap.add_argument("--env", default="prod")
    ap.add_argument("--wait", action="store_true")
    ap.add_argument("--until", choices=["deployable", "deployed"], default="deployable")
    ap.add_argument("--timeout", type=int, default=1800, help="seconds for --wait (default 1800)")
    ap.add_argument("--smoke-job", default="smoke:post-deploy", help="post-deploy job to wait for")
    ap.add_argument("--trace", metavar="JOB", help="print the tail of this job's log and exit")
    ap.add_argument("--lines", type=int, default=60)
    args = ap.parse_args()

    tok = token(args.token)
    mods = projects()
    if args.module not in mods:
        print(f"pipeline-status: unknown module {args.module!r} (valid: {', '.join(mods)})", file=sys.stderr)
        return 2
    project = mods[args.module]
    base = f"/projects/{pid(project)}"

    try:
        tag = args.tag or api(tok, "GET", f"{base}/repository/tags",
                              query={"order_by": "version", "per_page": 1})[0]["name"]
        pipes = api(tok, "GET", f"{base}/pipelines",
                    query={"ref": tag, "order_by": "id", "sort": "desc", "per_page": 1})
    except (RuntimeError, IndexError, KeyError) as exc:
        print(f"pipeline-status: {exc}", file=sys.stderr)
        return 2
    if not pipes:
        print(f"pipeline-status: no pipeline for {args.module} {tag} yet", file=sys.stderr)
        return 2
    pl = pipes[0]["id"]

    def jobs():
        return sorted(api(tok, "GET", f"{base}/pipelines/{pl}/jobs", query={"per_page": 100}),
                      key=lambda j: j["id"])

    if args.trace:
        for j in jobs():
            if j["name"] == args.trace:
                text = api(tok, "GET", f"{base}/jobs/{j['id']}/trace", raw=True)
                out = "\n".join(text.splitlines()[-args.lines:])
                sys.stdout.buffer.write(f"{j['name']} [{j['status']}]\n{out}\n".encode("utf-8", "replace"))
                return 0
        print(f"pipeline-status: no job named {args.trace!r}", file=sys.stderr)
        return 2

    env = args.env
    deadline = time.time() + args.timeout
    last = None
    while True:
        js = jobs()
        state = {j["name"]: j["status"] for j in js}
        blocking = [j["name"] for j in js if j["status"] in BAD and not j.get("allow_failure")]
        deploy_name = next((n for n in state if n == f"deploy:{env}" or n.startswith(f"deploy:{env}:")),
                           "deploy" if "deploy" in state else None)
        deploy = state.get(deploy_name) if deploy_name else None
        smoke = state.get(args.smoke_job)
        upstream_done = all(j["status"] in ("success", "skipped", "manual") or j.get("allow_failure")
                            for j in js if j["stage"] in ("verify", "build", "scan", "test"))

        if blocking:
            verdict, code = f"BLOCKED by {', '.join(blocking)} - the deploy job will show 'skipped'", 1
        elif deploy_name is None and upstream_done:
            verdict, code = "BUILT - this pipeline has no deploy job (build-only module)", 0
        elif args.until == "deployable" and deploy == "manual":
            verdict, code = f"DEPLOYABLE - {deploy_name} is waiting to be played", 0
        elif deploy == "success" and smoke not in ("created", "pending", "running"):
            verdict, code = f"DEPLOYED - {deploy_name} success, {args.smoke_job} {smoke}", 0
        elif deploy == "skipped":
            verdict, code = f"BLOCKED - {deploy_name} skipped (an upstream gate did not pass)", 1
        else:
            verdict, code = None, None

        snapshot = json.dumps(state, sort_keys=True)
        if snapshot != last or verdict:
            print(f"{args.module} {tag} | pipeline {pl} | {gitlab_url()}/{project}/-/pipelines/{pl}")
            for j in js:
                note = "  (allow_failure)" if j.get("allow_failure") and j["status"] in BAD else ""
                print(f"  {j['stage']:12} {j['name']:28} {j['status']}{note}")
            last = snapshot
        if verdict:
            print(verdict)
            return code
        if not args.wait:
            return 0
        if time.time() > deadline:
            print(f"TIMEOUT after {args.timeout}s - pipeline still running")
            return 3
        sys.stdout.flush()
        time.sleep(20)


if __name__ == "__main__":
    sys.exit(main())
