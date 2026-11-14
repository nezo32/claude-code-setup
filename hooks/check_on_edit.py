"""PostToolUse: run a project checker on files Claude just wrote, and push hits back.

Wire it as a PostToolUse hook on Write|Edit|MultiEdit (see settings.example.json).
When a written file lives under one of the configured directories, the hook runs the
configured command on it. If the command exits with the "hit" code, its output is
returned to Claude as a blocking reason, so the text gets fixed before anyone sees it.

Typical uses: a banned-words / content-policy checker over user-facing copy, a
linter over a docs folder, a schema validator over config files.

Config: JSON at $CLAUDE_CHECK_CONFIG, else <project>/.claude/hooks/check_on_edit.json:

  {
    "rules": [
      {
        "dirs": ["content", "docs/public"],
        "command": ["python", "tools/content_check.py", "{file}", "--profile", "{profile}"],
        "hit_exit_code": 1,
        "profiles": {"*_social*": "strict", "*": "default"}
      }
    ]
  }

"{file}" is replaced with the absolute path, "{profile}" with the first matching
glob in "profiles" (matched against the project-relative POSIX path). No config ->
the hook does nothing. Fails open on its own errors.
"""
import fnmatch
import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT = Path(os.environ.get("CLAUDE_PROJECT_DIR", Path(__file__).resolve().parents[2])).resolve()


def load_rules():
    path = os.environ.get("CLAUDE_CHECK_CONFIG") or str(PROJECT / ".claude" / "hooks" / "check_on_edit.json")
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh).get("rules", [])
    except FileNotFoundError:
        return []


def profile_for(rel_posix, profiles):
    for pattern, name in (profiles or {}).items():
        if fnmatch.fnmatch(rel_posix, pattern):
            return name
    return "default"


def main():
    data = json.load(sys.stdin)
    path = (data.get("tool_input") or {}).get("file_path")
    if not path:
        return
    p = Path(path)
    p = p if p.is_absolute() else PROJECT / p
    try:
        r = p.resolve().relative_to(PROJECT)
    except ValueError:
        return
    if not r.parts or not p.exists():
        return
    rel_posix = r.as_posix()

    for rule in load_rules():
        dirs = [d.strip("/") for d in rule.get("dirs", [])]
        if not any(rel_posix == d or rel_posix.startswith(d + "/") for d in dirs):
            continue
        prof = profile_for(rel_posix, rule.get("profiles"))
        cmd = [part.replace("{file}", str(p)).replace("{profile}", prof) for part in rule["command"]]
        res = subprocess.run(cmd, cwd=PROJECT, capture_output=True, text=True, encoding="utf-8")
        if res.returncode == rule.get("hit_exit_code", 1):
            print(json.dumps({
                "decision": "block",
                "reason": f"Checker hits in {rel_posix} (profile={prof}). Rewrite these lines:\n"
                          f"{res.stdout.strip()}",
            }))
            return


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"check_on_edit hook error: {e}", file=sys.stderr)
        sys.exit(0)
