import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from . import config
from .sensitive import scan_text


class GitError(Exception):
    pass


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=300, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    except FileNotFoundError:
        raise GitError("Git is not installed or not on PATH.") from None
    except subprocess.TimeoutExpired:
        raise GitError("A Git command timed out.") from None


def _git(args: list[str], cwd: Path, secret: str = "") -> str:
    p = _run(args, cwd)
    if p.returncode != 0:
        err = (p.stderr or p.stdout or "unknown error").strip()
        if secret:
            err = err.replace(secret, "***")
        raise GitError(f"git {args[-1] if args[0] == '-c' else args[0]} failed: {err[:500]}")
    return p.stdout


def check_git() -> None:
    if not shutil.which("git"):
        raise GitError("Git is not installed or not on PATH.")


def init_repo(folder: Path) -> None:
    if not (folder / ".git").exists():
        _git(["init"], folder)
        _git(["symbolic-ref", "HEAD", "refs/heads/main"], folder)
    reset_index(folder)


def reset_index(folder: Path) -> None:
    _run(["reset", "-q"], folder)


def _mit(name: str) -> str:
    return f"""MIT License

Copyright (c) {datetime.now().year} {name} contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""


def write_meta(folder: Path, plan, blocked: set[str]) -> list[str]:
    """Write approved README/.gitignore/LICENSE; return meta files to commit."""
    texts = {".gitignore": plan.gitignore, "README.md": plan.readme,
             "LICENSE": _mit(plan.repo_name) if plan.license == "MIT" else ""}
    out = []
    for name, text in texts.items():
        if name in blocked:
            continue
        path = folder / name
        if text.strip():
            path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")
            out.append(name)
        elif path.exists():
            out.append(name)
    return out


def commit(folder: Path, message: str, files: list[str]) -> bool:
    for i in range(0, len(files), 100):
        _git(["add", "-f", "--", *files[i:i + 100]], folder)
    if _run(["diff", "--cached", "--quiet"], folder).returncode == 0:
        return False
    ident = [] if _run(["config", "user.name"], folder).stdout.strip() else [
        "-c", "user.name=RepoPilot", "-c", "user.email=repopilot@users.noreply.github.com"]
    _git([*ident, "commit", "-m", message], folder)
    return True


def push(folder: Path, clone_url: str) -> None:
    token = config.GITHUB_TOKEN
    if _run(["remote", "get-url", "origin"], folder).returncode == 0:
        _git(["remote", "set-url", "origin", clone_url], folder)
    else:
        _git(["remote", "add", "origin", clone_url], folder)
    auth_url = clone_url.replace("https://", f"https://x-access-token:{token}@", 1)
    _git(["push", auth_url, "HEAD:refs/heads/main"], folder, secret=token)


# ---- existing repository support ----
def repo_info(folder: Path) -> dict:
    """Validate that `folder` is a repo root with a GitHub origin. Never returns the raw remote URL."""
    if not (folder / ".git").exists():
        raise GitError("This folder is not a Git repository.")
    top = _git(["rev-parse", "--show-toplevel"], folder).strip()
    if not os.path.samefile(top, folder):
        raise GitError("Select the root folder of the repository (the one that contains .git).")
    p = _run(["remote", "get-url", "origin"], folder)
    if p.returncode != 0:
        raise GitError("This repository has no 'origin' remote.")
    m = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?/?$", p.stdout.strip())
    if not m:
        raise GitError("The 'origin' remote is not a GitHub repository.")
    q = _run(["symbolic-ref", "--short", "HEAD"], folder)
    if q.returncode != 0:
        raise GitError("No branch is checked out. Check out a branch first.")
    branch = q.stdout.strip()
    if _run(["rev-parse", "--verify", "-q", f"origin/{branch}"], folder).returncode == 0:
        r = _run(["rev-list", "--count", f"origin/{branch}..HEAD"], folder)
    else:
        r = _run(["rev-list", "--count", "HEAD"], folder)
    ahead = int(r.stdout.strip() or 0) if r.returncode == 0 else 0
    return {"owner": m[1], "name": m[2], "branch": branch, "ahead": ahead,
            "clone_url": f"https://github.com/{m[1]}/{m[2]}.git"}


def changes(folder: Path) -> list[dict]:
    """Uncommitted changes as [{path, status}], status: M modified, A/? new, D deleted."""
    ent = _git(["status", "--porcelain=v1", "-z", "--untracked-files=all"], folder).split("\0")
    out: list[dict] = []
    i = 0
    while i < len(ent):
        e = ent[i]
        i += 1
        if len(e) < 4:
            continue
        xy, path = e[:2], e[3:]
        old = None
        if "R" in xy or "C" in xy:
            old = ent[i] if i < len(ent) else None
            i += 1
        if xy == "??":
            st = "?"
        elif not (folder / path).exists():
            st = "D"
        elif "A" in xy:
            st = "A"
        else:
            st = "M"
        out.append({"path": path, "status": st})
        if old and "R" in xy:
            out.append({"path": old, "status": "D"})
    return out


def _diff(folder: Path, path: str) -> str:
    p = _run(["diff", "HEAD", "--", path], folder)
    text = p.stdout if p.returncode == 0 else ""
    return "" if scan_text(path, text) else text[:1500]  # skip diffs that touch anything secret-like


def restrict_to_changes(folder: Path, s: dict) -> dict:
    """Narrow a full scan to changed files; snippets become diffs (only when they are secret-free)."""
    ch = changes(folder)
    by = {c["path"]: c["status"] for c in ch}
    files = [{**f, "status": by[f["path"]]} for f in s["files"] if f["path"] in by]
    files += [{"path": p, "size": 0, "status": "D"} for p, st in by.items() if st == "D"]
    blocked = [b for b in s["blocked"] if b["path"] in by]
    names = {b["path"] for b in blocked}
    snippets: dict[str, str] = {}
    for f in files[:25]:
        if f["status"] == "M":
            d = _diff(folder, f["path"])
            if d:
                snippets[f["path"]] = d
        elif f["status"] in ("A", "?") and f["path"] in s["snippets"]:
            snippets[f["path"]] = s["snippets"][f["path"]]
    return {**s, "files": files, "blocked": blocked, "snippets": snippets, "changes": ch,
            "findings": [x for x in s["findings"] if x["file"] in names]}


def _auth(url: str) -> str:
    return url.replace("https://", f"https://x-access-token:{config.GITHUB_TOKEN}@", 1)


def behind(folder: Path, clone_url: str, branch: str) -> int:
    """How many commits the remote branch has that the local HEAD lacks."""
    token = config.GITHUB_TOKEN
    p = _run(["fetch", _auth(clone_url), f"refs/heads/{branch}"], folder)
    if p.returncode != 0:
        err = (p.stderr or "").replace(token, "***")
        if "couldn't find remote ref" in err:
            return 0
        raise GitError(f"Could not reach GitHub: {err.strip()[:300]}")
    return int(_git(["rev-list", "--count", "HEAD..FETCH_HEAD"], folder).strip() or 0)


def push_branch(folder: Path, clone_url: str, branch: str) -> None:
    _git(["push", _auth(clone_url), f"HEAD:refs/heads/{branch}"], folder, secret=config.GITHUB_TOKEN)
