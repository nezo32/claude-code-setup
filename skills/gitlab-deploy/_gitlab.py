"""Shared config and API helper for trigger-deploy.py and pipeline-status.py.

Everything project-specific comes from the environment (or a gitignored .env next
to these scripts). Nothing about any particular GitLab instance is hard-coded.

  GITLAB_URL          base URL of the GitLab instance, e.g. https://gitlab.example.com
  GITLAB_TOKEN        personal access token with `api` scope
  GITLAB_PROJECTS     module -> project path map: "web=group/web,api=group/api-server"
  GITLAB_BUILD_ONLY   space-separated modules whose pipelines have no deploy job
  GITLAB_ALL_ORDER    space-separated deploy order for `all` (default: map order)

Token precedence: --token > $GITLAB_TOKEN > .env file next to this script.
"""
import json
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request

_ENV_FILE = pathlib.Path(__file__).with_name(".env")


def _dotenv():
    vals = {}
    try:
        for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            vals[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return vals


_DOT = _dotenv()


def setting(name, default=None):
    return os.environ.get(name) or _DOT.get(name) or default


def die(msg, code=2):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def gitlab_url():
    url = setting("GITLAB_URL")
    if not url:
        die("GITLAB_URL is not set (env or .env next to the script)")
    return url.rstrip("/")


def token(cli=None):
    tok = cli or setting("GITLAB_TOKEN")
    if not tok:
        die("no token: set GITLAB_TOKEN (env or the gitignored .env next to the script) or pass --token")
    return tok


def projects():
    """Ordered dict module -> project path, from GITLAB_PROJECTS."""
    raw = setting("GITLAB_PROJECTS", "")
    out = {}
    for pair in filter(None, (p.strip() for p in raw.split(","))):
        if "=" not in pair:
            die(f"GITLAB_PROJECTS entry {pair!r} is not module=group/project")
        k, _, v = pair.partition("=")
        out[k.strip()] = v.strip()
    if not out:
        die("GITLAB_PROJECTS is empty, e.g. GITLAB_PROJECTS='web=group/web,api=group/api'")
    return out


def build_only():
    return set(setting("GITLAB_BUILD_ONLY", "").split())


def all_order():
    order = setting("GITLAB_ALL_ORDER", "").split()
    return order or list(projects())


def pid(project):
    return urllib.parse.quote(project, safe="")


def api(tok, method, path, *, query=None, raw=False):
    """Call the GitLab v4 API. Returns parsed JSON, raw text, or None on 204."""
    url = gitlab_url() + "/api/v4" + path
    if query:
        url += "?" + urllib.parse.urlencode(query)
    req = urllib.request.Request(url, method=method)
    req.add_header("PRIVATE-TOKEN", tok)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"HTTP {e.code} {method} {path}: {detail[:300]}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"cannot reach GitLab: {e.reason}") from None
    if raw:
        return body.decode("utf-8", "replace")
    return json.loads(body) if body else None
