import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

NAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
META_FILES = {"README.md", ".gitignore", "LICENSE"}


def _check_name(v: str) -> str:
    v = v.strip()
    if not NAME_RE.match(v) or v in (".", "..") or v.endswith(".git"):
        raise ValueError("Repository name may only contain letters, numbers, '.', '-' and '_'")
    return v


class Commit(BaseModel):
    message: str
    files: list[str]
    reason: str = ""

    @field_validator("message")
    @classmethod
    def _msg(cls, v: str) -> str:
        v = v.strip()
        if not 3 <= len(v) <= 200 or "\n" in v:
            raise ValueError("Commit messages must be a single line of 3-200 characters")
        return v


class Plan(BaseModel):
    repo_name: str
    description: str = Field(default="", max_length=350)
    topics: list[str] = []
    visibility: Literal["public", "private"] = "private"
    commits: list[Commit]
    readme: str = ""
    gitignore: str = ""
    license: Literal["MIT", "none"] = "none"
    warnings: list[str] = []

    @field_validator("repo_name")
    @classmethod
    def _name(cls, v: str) -> str:
        return _check_name(v)

    @field_validator("license", mode="before")
    @classmethod
    def _lic(cls, v: object) -> str:
        return "MIT" if str(v).strip().upper() == "MIT" else "none"

    @field_validator("topics")
    @classmethod
    def _topics(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        for t in v:
            t = re.sub(r"[^a-z0-9-]", "", t.strip().lower().replace(" ", "-").replace("_", "-"))[:50]
            if t and t not in out:
                out.append(t)
        return out[:20]


class JobCreate(BaseModel):
    folder: str
    repo_name: str
    description: str = Field(default="", max_length=350)
    visibility: Literal["public", "private"] = "private"

    @field_validator("repo_name")
    @classmethod
    def _name(cls, v: str) -> str:
        return _check_name(v)


class ApproveIn(BaseModel):
    acknowledge_warnings: bool = False


def validate_plan(plan: Plan, allowed: set[str], blocked: set[str], autofill: bool = False) -> Plan:
    seen: set[str] = set()
    commits: list[Commit] = []
    for c in plan.commits:
        files: list[str] = []
        for raw in c.files:
            f = raw.replace("\\", "/").removeprefix("./")
            if f in META_FILES:
                continue
            if f in blocked:
                raise ValueError(f"'{f}' is blocked for security reasons and cannot be committed")
            if f not in allowed:
                raise ValueError(f"File not found in the project: {f}")
            if f in seen:
                raise ValueError(f"File assigned to more than one commit: {f}")
            seen.add(f)
            files.append(f)
        if not files:
            if c.files:
                continue
            raise ValueError(f"Commit group is empty: {c.message}")
        commits.append(c.model_copy(update={"files": files}))
    rest = sorted(allowed - META_FILES - seen)
    if autofill and rest:
        commits.append(Commit(message="chore: add remaining project files", files=rest, reason="Files not grouped by the agent"))
    if not commits:
        raise ValueError("The plan contains no commits")
    return plan.model_copy(update={"commits": commits})
