import math
import re
from collections import Counter


def finding(sev: str, file: str, line: int, typ: str) -> dict:
    """Findings never contain the matched value."""
    return {"severity": sev, "file": file, "line": line, "type": typ,
            "message": f"{typ} detected. File excluded from push."}


_PATTERNS = [
    ("Groq API key", "high", re.compile(r"gsk_[A-Za-z0-9]{20,}")),
    ("GitHub token", "high", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})")),
    ("AWS access key", "high", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("Google API key", "high", re.compile(r"AIza[0-9A-Za-z_\-]{35}")),
    ("Private key", "high", re.compile(r"-----BEGIN (?:[A-Z]+ )*PRIVATE KEY(?: BLOCK)?-----")),
    ("JWT-like secret", "medium", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("Connection string with credentials", "high", re.compile(r"\b[a-z][a-z0-9+.\-]*://[^\s:/@]+:[^\s@/]+@[^\s/]+")),
    ("Hard-coded credential", "medium", re.compile(
        r"(?i)\b(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token)\b\s*[:=]\s*['\"][^'\"\s$]{6,}['\"]")),
]
_PLACEHOLDERS = ("example", "your_", "your-", "changeme", "xxxx", "placeholder", "dummy", "<", "${")
_TOKEN = re.compile(r"[A-Za-z0-9_\-]{32,}")
_KEY_EXT = (".pem", ".key", ".p12", ".pfx", ".ppk", ".jks", ".keystore")
_KEY_NAMES = {"id_rsa", "id_dsa", "id_ecdsa", "id_ed25519"}
_CRED_NAMES = {"credentials.json", "secrets.json", "service-account.json", ".npmrc", ".pypirc", ".netrc", "credentials"}


def _entropy(s: str) -> float:
    n = len(s)
    return -sum(v / n * math.log2(v / n) for v in Counter(s).values())


def blocked_name(rel: str) -> list[dict]:
    n = rel.rsplit("/", 1)[-1].lower()
    if n == ".env" or (n.startswith(".env.") and not n.endswith((".example", ".sample", ".template"))):
        return [finding("high", rel, 0, "Environment file")]
    if n in _KEY_NAMES or n.endswith(_KEY_EXT):
        return [finding("high", rel, 0, "Private key file")]
    if n in _CRED_NAMES or (n.startswith("secret") and n.rsplit(".", 1)[-1] in ("json", "yaml", "yml", "txt", "toml", "ini")):
        return [finding("high", rel, 0, "Credential file")]
    return []


def scan_text(rel: str, text: str, skip_entropy: bool = False) -> list[dict]:
    out: list[dict] = []
    for i, raw in enumerate(text.splitlines(), 1):
        line = raw[:4000]
        low = line.lower()
        placeholder = any(p in low for p in _PLACEHOLDERS)
        for typ, sev, rx in _PATTERNS:
            if rx.search(line) and not (typ == "Hard-coded credential" and placeholder):
                out.append(finding(sev, rel, i, typ))
        if not skip_entropy and not placeholder:
            for tok in _TOKEN.findall(line):
                if _entropy(tok) > 4.5 and not re.fullmatch(r"[0-9a-fA-F]+", tok):
                    out.append(finding("medium", rel, i, "High-entropy string"))
                    break
        if len(out) >= 20:
            break
    return out
