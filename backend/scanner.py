import json
import os
from pathlib import Path

from . import config
from .sensitive import blocked_name, finding, scan_text

IGNORE_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".next", ".nuxt", "dist", "build",
               "coverage", ".idea", ".vscode", ".pytest_cache", ".mypy_cache", ".gradle", "target", ".turbo", ".cache"}
IGNORE_FILES = {".DS_Store", "Thumbs.db", "desktop.ini"}
BINARY_EXT = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".pdf", ".zip", ".gz", ".tar", ".7z", ".exe",
              ".dll", ".so", ".woff", ".woff2", ".ttf", ".eot", ".mp3", ".mp4", ".mov", ".db", ".sqlite",
              ".sqlite3", ".class", ".jar", ".bin"}
LANGS = {".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript",
         ".java": "Java", ".go": "Go", ".rs": "Rust", ".rb": "Ruby", ".php": "PHP", ".cs": "C#", ".cpp": "C++",
         ".c": "C", ".swift": "Swift", ".kt": "Kotlin", ".html": "HTML", ".css": "CSS", ".sh": "Shell", ".sql": "SQL"}
CONFIG_NAMES = {"package.json", "requirements.txt", "pyproject.toml", "Cargo.toml", "go.mod", "pom.xml",
                "Dockerfile", "docker-compose.yml", "tsconfig.json", "setup.py", "Makefile"}
PACKAGE_MANAGERS = {"package-lock.json": "npm", "yarn.lock": "yarn", "pnpm-lock.yaml": "pnpm", "requirements.txt": "pip",
                    "pyproject.toml": "pyproject", "Pipfile": "pipenv", "Cargo.toml": "cargo", "go.mod": "go", "pom.xml": "maven"}
JS_FRAMEWORKS = ("react", "vue", "next", "svelte", "express", "vite", "angular", "tailwindcss")
PY_FRAMEWORKS = ("fastapi", "django", "flask", "streamlit", "pytest", "sqlalchemy")
NO_ENTROPY = ("lock", ".lock.json", "-lock.json", ".min.js", ".min.css", ".svg", ".map", "lock.yaml")
MAX_FILES = 3000


def resolve_folder(raw: str) -> Path:
    if not raw or not raw.strip() or "\0" in raw:
        raise ValueError("Enter a valid folder path.")
    try:
        p = Path(raw.strip().strip('"')).expanduser().resolve(strict=True)
    except (OSError, RuntimeError):
        raise ValueError("Folder not found. Check the path and try again.") from None
    if not p.is_dir():
        raise ValueError("The path is not a folder.")
    if p == Path(p.anchor) or p == Path.home():
        raise ValueError("Choose a project folder, not a drive root or your home folder.")
    try:
        next(p.iterdir(), None)
    except PermissionError:
        raise ValueError("RepoPilot does not have permission to read this folder.") from None
    return p


def scan(folder: Path) -> dict:
    """Read-only scan. Files with findings are moved to `blocked` and never read again."""
    files, blocked, findings, snippets = [], [], [], {}
    langs: dict[str, int] = {}
    frameworks: set[str] = set()
    managers: set[str] = set()
    budget, count, truncated = 40000, 0, False
    limit = config.MAX_FILE_SIZE_MB * 1024 * 1024
    for root, dirs, names in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if d not in IGNORE_DIRS and not d.endswith(".egg-info"))
        for n in sorted(names):
            if n in IGNORE_FILES or n.endswith((".pyc", ".pyo", ".swp", ".log")):
                continue
            full = Path(root) / n
            if full.is_symlink():
                continue
            count += 1
            if count > MAX_FILES:
                truncated = True
                continue
            rel = full.relative_to(folder).as_posix()
            try:
                size = full.stat().st_size
            except OSError:
                continue
            ext = full.suffix.lower()
            text = None
            found = blocked_name(rel)
            if not found:
                if size > limit:
                    found = [finding("medium", rel, 0, "File larger than the configured size limit")]
                elif ext not in BINARY_EXT and size <= 1_000_000:
                    try:
                        data = full.read_bytes()
                    except OSError:
                        data = b"\0"
                    if b"\0" not in data:
                        text = data.decode("utf-8", errors="replace")
                        found = scan_text(rel, text, skip_entropy=n.lower().endswith(NO_ENTROPY))
            if found:
                findings += found
                blocked.append({"path": rel, "reason": found[0]["type"]})
                continue
            files.append({"path": rel, "size": size})
            if ext in LANGS:
                langs[LANGS[ext]] = langs.get(LANGS[ext], 0) + 1
            if n in PACKAGE_MANAGERS:
                managers.add(PACKAGE_MANAGERS[n])
            if text is not None and n == "package.json":
                try:
                    pkg = json.loads(text)
                    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                    frameworks |= {f for f in JS_FRAMEWORKS if f in deps}
                except (ValueError, AttributeError):
                    pass
            if text is not None and n in ("requirements.txt", "pyproject.toml"):
                frameworks |= {f for f in PY_FRAMEWORKS if f in text.lower()}
            if text is not None and budget > 0 and len(snippets) < 25 and (ext in LANGS or n in CONFIG_NAMES):
                snip = "\n".join(text.splitlines()[:40])[:1200]
                snippets[rel] = snip
                budget -= len(snip)
    root_names = {f["path"].lower() for f in files if "/" not in f["path"]}
    return {"files": files, "blocked": blocked, "findings": findings, "snippets": snippets, "truncated": truncated,
            "languages": sorted(langs, key=langs.get, reverse=True), "frameworks": sorted(frameworks),
            "package_managers": sorted(managers), "has_readme": "readme.md" in root_names,
            "has_gitignore": ".gitignore" in root_names, "has_license": "license" in root_names}
