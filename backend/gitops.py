import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from . import config


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
