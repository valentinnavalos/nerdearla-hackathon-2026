"""Where an experimental result comes from: branch + commit + date + SDK, stamped on every probe
report so results from roadmap, status and later changes never get mixed.

The Docker image has no git: the branch/commit are read from .git directly, and the host passes
GIT_DIRTY (0/1) and GIT_DIFF_SHA (sha256 of `git diff HEAD`) when it knows them."""

import os
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(["git", *args], capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _read_git_dir(root: Path) -> tuple[str | None, str | None]:
    git = root / ".git"
    try:
        head = (git / "HEAD").read_text().strip()
    except OSError:
        return None, None
    if not head.startswith("ref: "):
        return None, head  # detached HEAD
    ref = head[5:]
    branch = ref.removeprefix("refs/heads/")
    ref_file = git / ref
    if ref_file.exists():
        return branch, ref_file.read_text().strip()
    packed = git / "packed-refs"
    if packed.exists():
        for line in packed.read_text().splitlines():
            if line.endswith(" " + ref):
                return branch, line.split(" ", 1)[0]
    return branch, None


def git_meta(root: Path = Path(".")) -> dict:
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    commit = _git("rev-parse", "HEAD")
    dirty = None
    if commit is not None:
        dirty = bool(_git("status", "--porcelain", "--untracked-files=no"))
    else:
        branch, commit = _read_git_dir(root)
    if os.getenv("GIT_DIRTY") in ("0", "1"):
        dirty = os.getenv("GIT_DIRTY") == "1"
    return {
        "branch": branch,
        "commit": commit[:12] if commit else None,
        "dirty": dirty,  # True = the code measured is this commit + uncommitted changes
        "diff_sha": os.getenv("GIT_DIFF_SHA") or None,
    }


def run_meta(args=None, **extra) -> dict:
    try:
        from google import genai

        genai_version = genai.__version__
    except Exception:
        genai_version = None
    return {
        "date": datetime.now().astimezone().isoformat(timespec="seconds"),
        **git_meta(),
        "python": platform.python_version(),
        "google_genai": genai_version,
        "argv": sys.argv,
        "args": {k: v for k, v in vars(args).items()} if args is not None else None,
        **extra,
    }
