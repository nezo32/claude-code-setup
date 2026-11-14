"""Pack a status report and every file it references into one zip (skill /analyst-report).

The analyst has no repo access, so the report ships with its sources. This script refuses
anything that must never leave the machine: secret files (.env*), blocked folders, model
weights, media and other binaries, and any text file containing a token-like string.

Usage (repo root, stdlib only, Python 3.9+):
    python .claude/skills/analyst-report/pack_report.py <files_list.txt> <out.zip> [--dry-run] [--force] [--max-mb 25]

Files list: one repo-relative path per line (forward or back slashes); blank lines and
`# comments` ignored; a directory entry adds every file under it except __pycache__ (same
checks apply). Zip entries keep their repo-relative paths.

Env:
    PACK_ROOT          root that paths resolve against (default: repo root)
    PACK_BLOCKED_DIRS  extra top-level folders to refuse, space-separated
    PACK_SECRET_VARS   extra variable names whose literal assignment counts as a secret

Exit codes: 0 ok, 1 refused (nothing written), 2 usage error.
Refusals print the file and line only, never the matched text.
"""
import argparse
import os
import re
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]

BLOCKED_TOP = {".git", "node_modules", "datasets", "output", "outputs", "archive", "weights", "models"}
BLOCKED_TOP |= {d.lower() for d in os.environ.get("PACK_BLOCKED_DIRS", "").split()}

MEDIA_EXT = {
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".heic", ".avif", ".psd",
    ".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v",
    ".wav", ".mp3", ".flac", ".ogg", ".m4a", ".opus", ".aac",
    ".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".onnx", ".gguf", ".npy", ".npz",
    ".zip", ".7z", ".rar", ".tar", ".gz", ".sqlite", ".db", ".exe", ".dll", ".pyc",
}

SECRET_VARS = ["HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN", "GITLAB_TOKEN",
               "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "AWS_SECRET_ACCESS_KEY", "API_KEY", "SECRET_KEY"]
SECRET_VARS += os.environ.get("PACK_SECRET_VARS", "").split()

# Names only are reported, never the matched text. Prefixes are the providers' public formats.
SECRET_PATTERNS = [
    ("huggingface token", re.compile(r"\bhf_[A-Za-z0-9]{30,}")),
    ("github token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}")),
    ("github fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}")),
    # Prefixes are split so this file does not itself trip secret scanners.
    ("gitlab token", re.compile(r"\bgl" r"pat-[A-Za-z0-9_\-]{20,}")),
    ("openai-style key", re.compile(r"\bs" r"k-[A-Za-z0-9_\-]{32,}")),
    ("aws access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("secret assignment", re.compile(
        r"\b(?:" + "|".join(map(re.escape, SECRET_VARS)) + r")"
        r"\s*[:=]\s*['\"]?(?!\$|<|%|\{)[A-Za-z0-9_\-]{16,}")),
    ("auth header", re.compile(r"Authorization:\s*(?:Basic|Bearer)\s+(?!\$)[A-Za-z0-9+/=_\-.]{20,}")),
]


def root_dir():
    return Path(os.environ.get("PACK_ROOT") or REPO).resolve()


def read_list(path):
    out = []
    for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            out.append(s.replace("\\", "/"))
    return out


def check_path(rel, root):
    """Return (resolved Path, None) or (None, reason)."""
    p = (root / rel).resolve()
    try:
        r = p.relative_to(root)
    except ValueError:
        return None, "outside the root"
    parts = r.parts
    if not parts:
        return None, "is the root itself"
    if parts[0].lower() in BLOCKED_TOP:
        return None, f"blocked folder {parts[0]}/"
    if any(x.lower().startswith(".env") and x.lower() != ".env.example" for x in parts):
        return None, "secret env file"
    if p.is_file() and p.suffix.lower() in MEDIA_EXT:
        return None, f"binary/media file ({p.suffix.lower()})"
    return p, None


def scan_text(p):
    data = p.read_bytes()
    if b"\x00" in data[:8192]:
        return "binary content (NUL bytes)"
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return "not UTF-8 text"
    for name, rx in SECRET_PATTERNS:
        m = rx.search(text)
        if m:
            return f"token-like string ({name}) at line {text.count(chr(10), 0, m.start()) + 1}"
    return None


def collect(entries, root):
    files, errors, seen = [], [], set()
    for rel in entries:
        p, why = check_path(rel, root)
        if why:
            errors.append(f"{rel}: {why}")
            continue
        if not p.exists():
            errors.append(f"{rel}: missing")
            continue
        cands = (sorted(x for x in p.rglob("*") if x.is_file() and "__pycache__" not in x.parts)
                 if p.is_dir() else [p])
        for f in cands:
            frel = f.relative_to(root).as_posix()
            _, why = check_path(frel, root)
            why = why or scan_text(f)
            if why:
                errors.append(f"{frel}: {why}")
            elif frel not in seen:
                seen.add(frel)
                files.append((f, frel))
    return files, errors


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files_list", help="text file: one repo-relative path per line")
    ap.add_argument("out_zip", help="output zip, kept out of git")
    ap.add_argument("--dry-run", action="store_true", help="check and list, write nothing")
    ap.add_argument("--force", action="store_true", help="overwrite an existing zip")
    ap.add_argument("--max-mb", type=float, default=25.0, help="refuse if the zip is larger (default 25)")
    a = ap.parse_args(argv)

    root = root_dir()
    lst = Path(a.files_list)
    lst = lst if lst.is_absolute() else root / lst
    if not lst.is_file():
        print(f"files list not found: {lst}", file=sys.stderr)
        return 2
    out = Path(a.out_zip)
    out = (out if out.is_absolute() else root / out).resolve()
    if out.suffix.lower() != ".zip":
        print("out_zip must end with .zip", file=sys.stderr)
        return 2
    try:
        top = out.relative_to(root).parts[0].lower()
        if top in BLOCKED_TOP:
            print(f"refusing to write into {top}/", file=sys.stderr)
            return 2
    except (ValueError, IndexError):
        pass
    if out.exists() and not a.force and not a.dry_run:
        print(f"{out} exists; bump the name or pass --force", file=sys.stderr)
        return 2

    entries = read_list(lst)
    if not entries:
        print("files list is empty", file=sys.stderr)
        return 2
    files, errors = collect(entries, root)
    if errors:
        print("REFUSED - nothing written:", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        return 1

    raw = sum(f.stat().st_size for f, _ in files)
    for _, rel in files:
        print(f"  + {rel}")
    if a.dry_run:
        print(f"dry-run: {len(files)} files, {raw / 1024:.1f} KB uncompressed -> {out}")
        return 0

    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".part")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f, rel in files:
            z.write(f, rel)
    size = tmp.stat().st_size
    if size > a.max_mb * 1024 * 1024:
        tmp.unlink()
        print(f"REFUSED: zip {size / 1048576:.1f} MB > --max-mb {a.max_mb:g}", file=sys.stderr)
        return 1
    os.replace(tmp, out)
    print(f"wrote {out} - {len(files)} files, {size / 1024:.1f} KB ({raw / 1024:.1f} KB uncompressed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
