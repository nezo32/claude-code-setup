"""PreToolUse guard: protected paths and secret files.

Wire it as a PreToolUse hook on Write|Edit|MultiEdit|NotebookEdit|Read|Bash|PowerShell
(see settings.example.json). It denies, with a reason Claude can act on:

  - deleting / moving / renaming anything under a "no_delete" directory
    (e.g. datasets/, archive/, model weights). The owner can still run it by hand.
  - overwriting an EXISTING file under a "no_overwrite" directory
    (creating new files there is allowed: write a new versioned file instead).
  - editing any file matching a "frozen_globs" pattern (e.g. "weights/**/*.safetensors").
  - reading secret files (.env and friends) into the conversation, via the Read tool
    or via cat/type/Get-Content/head/tail/... in a shell command.

Config: JSON file at $CLAUDE_GUARD_CONFIG, else <project>/.claude/hooks/guard.json,
else the defaults below. Example guard.json:

  {
    "no_delete":    ["datasets", "archive", "weights"],
    "no_overwrite": ["datasets", "archive"],
    "frozen_globs": ["weights/**/*.safetensors"],
    "secret_names": [".env", ".env.local", "credentials.json"]
  }

The hook fails open: a bug in it prints to stderr and lets the call through, so it
can never wedge a session. It is a seatbelt, not a sandbox: a determined shell command
can get around a regex. Pair it with permissions.deny in settings.json.
"""
import fnmatch
import json
import os
import re
import sys
from pathlib import Path

PROJECT = Path(os.environ.get("CLAUDE_PROJECT_DIR", Path(__file__).resolve().parents[2])).resolve()

DEFAULTS = {
    "no_delete": ["datasets", "archive"],
    "no_overwrite": ["datasets", "archive"],
    "frozen_globs": [],
    "secret_names": [".env"],
}


def load_config():
    cfg = dict(DEFAULTS)
    path = os.environ.get("CLAUDE_GUARD_CONFIG") or str(PROJECT / ".claude" / "hooks" / "guard.json")
    try:
        with open(path, encoding="utf-8") as fh:
            cfg.update(json.load(fh))
    except FileNotFoundError:
        pass
    return cfg


CFG = load_config()
NO_DELETE = [d.strip("/\\").lower() for d in CFG["no_delete"]]
NO_OVERWRITE = [d.strip("/\\").lower() for d in CFG["no_overwrite"]]
FROZEN = CFG["frozen_globs"]
SECRETS = CFG["secret_names"]

DESTRUCTIVE = re.compile(
    r"(?<![\w-])(rm|rmdir|del|erase|rd|mv|move|ren|rename|Remove-Item|Move-Item|Rename-Item|ri|mi|"
    r"Clear-Content|git\s+rm|git\s+clean|git\s+mv)(?![\w-])",
    re.IGNORECASE,
)
PROTECTED_TOKEN = (
    re.compile(r"(^|[\s\"'/\\=])(\./)?(" + "|".join(map(re.escape, NO_DELETE)) + r")([/\\\s\"']|$)", re.IGNORECASE)
    if NO_DELETE else None
)
SECRET_DUMP = re.compile(
    r"(?<![\w-])(cat|type|more|less|head|tail|Get-Content|gc|bat|strings|xxd|od)\b[^|;&]*("
    + "|".join(map(re.escape, SECRETS)) + r")(?![\w.])",
    re.IGNORECASE,
)


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))
    sys.exit(0)


def rel(path_str):
    """Path relative to the project, or None if it is outside it."""
    if not path_str:
        return None
    p = Path(path_str)
    if not p.is_absolute():
        p = PROJECT / p
    try:
        return p.resolve().relative_to(PROJECT)
    except ValueError:
        return None


def main():
    data = json.load(sys.stdin)
    tool = data.get("tool_name", "")
    inp = data.get("tool_input", {}) or {}

    if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        r = rel(inp.get("file_path") or inp.get("notebook_path") or "")
        if r is None or not r.parts:
            return
        top = r.parts[0].lower()
        if top in NO_OVERWRITE and (PROJECT / r).exists():
            deny(f"{r} is in {top}/: overwriting existing files there needs the owner's explicit OK. "
                 f"Write a new versioned file instead, or report it as an open decision.")
        posix = r.as_posix()
        for g in FROZEN:
            if fnmatch.fnmatch(posix, g):
                deny(f"{r} matches frozen pattern {g!r}: the agent never edits these files.")
        return

    if tool == "Read":
        r = rel(inp.get("file_path", ""))
        if r is not None and r.name in SECRETS:
            deny(f"{r.name} holds secrets: do not read it into the conversation. Load it in the command "
                 "instead, e.g. `set -a; . ./.env; set +a; <cmd>`, or let the program read it itself.")
        return

    if tool in ("Bash", "PowerShell"):
        cmd = inp.get("command", "")
        if SECRETS and SECRET_DUMP.search(cmd):
            deny("This command would print secret values. Source the file without echoing it instead.")
        if PROTECTED_TOKEN is None:
            return
        for segment in re.split(r"&&|\|\||;|\|", cmd):
            if DESTRUCTIVE.search(segment) and PROTECTED_TOKEN.search(segment):
                deny(f"Delete/move inside {', '.join(NO_DELETE)} needs the owner's decision. "
                     "Report it as an open decision; the owner can run it by hand.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # never break the session on a hook bug
        print(f"guard_protected hook error: {e}", file=sys.stderr)
        sys.exit(0)
