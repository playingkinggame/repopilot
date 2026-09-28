import json
import time
from typing import Callable

from groq import APIConnectionError, APIError, AuthenticationError, Groq, RateLimitError
from pydantic import ValidationError

from . import config
from .schemas import META_FILES, Plan, validate_plan

SYSTEM = """You are RepoPilot's planning agent. You only make decisions; the backend performs every action.
Workflow: call scan_folder, then scan_for_secrets, then propose_plan, then generate_readme, then reply DONE.
Rules: use only file paths returned by scan_folder. Every file must be in exactly one commit. Do not list README.md,
.gitignore or LICENSE in commits. Create 3-8 logical commits with Conventional Commit messages (chore/feat/fix/docs/test),
ordered from scaffolding and config to features to docs. Never guess or invent secrets. If propose_plan returns an error, fix it and call it again.
gitignore must suit the detected stack. license is "MIT" or "none"."""

SYSTEM_UPDATE = """You are RepoPilot's planning agent for an EXISTING GitHub repository. The user changed files locally; you only make decisions, the backend performs every action.
Workflow: call scan_folder (changed files with status M=modified, A or ?=new, D=deleted, plus diffs), then scan_for_secrets, then propose_plan, then reply DONE. Do not call generate_readme.
Group the changes into 1-5 logical commits with Conventional Commit messages that describe what changed (use the diffs). Every changed file, including deleted ones, must be in exactly one commit.
Use only paths from scan_folder. Leave gitignore empty and license "none". Never guess or invent secrets."""

COMMIT_SCHEMA = {"type": "object", "properties": {"message": {"type": "string"}, "files": {"type": "array", "items": {"type": "string"}},
                                                   "reason": {"type": "string"}}, "required": ["message", "files", "reason"]}
TOOLS = [
    {"type": "function", "function": {"name": "scan_folder", "description": "Get the safe file tree, languages, frameworks and trimmed snippets.",
                                      "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "scan_for_secrets", "description": "Get the list of files blocked by the local secret scanner (no values).",
                                      "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "propose_plan", "description": "Submit the Git publishing plan for validation.", "parameters": {
        "type": "object", "properties": {
            "repo_name": {"type": "string"}, "description": {"type": "string"}, "topics": {"type": "array", "items": {"type": "string"}},
            "visibility": {"type": "string", "enum": ["public", "private"]}, "commits": {"type": "array", "items": COMMIT_SCHEMA},
            "gitignore": {"type": "string"}, "license": {"type": "string", "enum": ["MIT", "none"]},
            "warnings": {"type": "array", "items": {"type": "string"}}},
        "required": ["repo_name", "description", "topics", "visibility", "commits"]}}},
    {"type": "function", "function": {"name": "generate_readme", "description": "Generate the README.md for the project.",
                                      "parameters": {"type": "object", "properties": {}}}},
]


class AgentError(Exception):
    pass


class Agent:
    def __init__(self, scan: dict, repo_name: str, description: str, visibility: str, log: Callable[[str], None], update: bool = False):
        self.scan, self.repo_name, self.description, self.visibility, self.log = scan, repo_name, description, visibility, log
        self.update = update
        self.tools = [t for t in TOOLS if not (update and t["function"]["name"] == "generate_readme")]
        self.allowed = {f["path"] for f in scan["files"]}
        self.blocked = {b["path"] for b in scan["blocked"]}
        self.plan: Plan | None = None
        self.readme = ""
        self.client = Groq(api_key=config.GROQ_API_KEY)

    def _chat(self, **kw):
        for attempt in range(4):
            try:
                return self.client.chat.completions.create(model=config.GROQ_MODEL, **kw)
            except RateLimitError:
                if attempt == 3:
                    raise AgentError("Groq rate limit reached. Wait a minute and try again.") from None
                time.sleep(2 * 2**attempt)
            except AuthenticationError:
                raise AgentError("Groq authentication failed. Check GROQ_API_KEY.") from None
            except APIConnectionError:
                raise AgentError("Could not reach Groq. Check your network connection.") from None
            except APIError as e:
                if attempt >= 2:
                    code = getattr(e, "status_code", "")
                    detail = str(getattr(e, "message", ""))[:300]
                    raise AgentError(f"Groq request failed ({e.__class__.__name__} {code}): {detail}") from None
        raise AgentError("Groq request failed.")

    def _summary(self) -> dict:
        s = self.scan
        return {"languages": s["languages"], "frameworks": s["frameworks"], "package_managers": s["package_managers"],
                "files": [[f["path"], f["size"], f.get("status", "")] for f in s["files"][:1500]], "truncated": s["truncated"],
                "has_readme": s["has_readme"], "has_gitignore": s["has_gitignore"], "has_license": s["has_license"]}

    def _tool(self, name: str, args: dict) -> dict:
        if name == "scan_folder":
            self.log("Analyzing project")
            return {**self._summary(), "snippets": self.scan["snippets"]}
        if name == "scan_for_secrets":
            self.log("Running security scan")
            return {"blocked_files": self.scan["blocked"], "note": "Blocked files are excluded and must not appear in the plan."}
        if name == "propose_plan":
            self.log("Generating plan")
            try:
                plan = Plan(**{**args, "readme": ""})
                self.plan = validate_plan(plan, self.allowed, self.blocked, autofill=True,
                                          meta=set() if self.update else META_FILES)
            except (ValidationError, ValueError, TypeError) as e:
                return {"error": str(e)[:800]}
            return {"ok": True, "commits": len(self.plan.commits)}
        if name == "generate_readme":
            self.log("Generating README")
            r = self._chat(messages=[
                {"role": "system", "content": "Write a concise, accurate README.md in Markdown for this project. Output only Markdown."},
                {"role": "user", "content": json.dumps({"name": self.repo_name, "description": self.description, **self._summary(),
                                                         "snippets": self.scan["snippets"]})}])
            self.readme = (r.choices[0].message.content or "").strip()
            return {"ok": True, "length": len(self.readme)}
        return {"error": f"Unknown tool: {name}"}

    def run(self) -> Plan:
        if not self.allowed:
            raise AgentError("No pushable files were found in this folder.")
        messages: list[dict] = [{"role": "system", "content": SYSTEM_UPDATE if self.update else SYSTEM},
                                {"role": "user", "content": json.dumps({"repo_name": self.repo_name, "description": self.description,
                                                                        "visibility": self.visibility})}]
        calls = 0
        for _ in range(config.MAX_AGENT_TOOL_CALLS + 3):
            msg = self._chat(messages=messages, tools=self.tools, tool_choice="auto").choices[0].message
            if not msg.tool_calls:
                break
            messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": [
                {"id": t.id, "type": "function", "function": {"name": t.function.name, "arguments": t.function.arguments or "{}"}}
                for t in msg.tool_calls]})
            for t in msg.tool_calls:
                calls += 1
                if calls > config.MAX_AGENT_TOOL_CALLS:
                    raise AgentError(f"The agent exceeded the limit of {config.MAX_AGENT_TOOL_CALLS} tool calls and was stopped.")
                try:
                    args = json.loads(t.function.arguments or "{}")
                    result = self._tool(t.function.name, args if isinstance(args, dict) else {})
                except json.JSONDecodeError:
                    result = {"error": "Arguments were not valid JSON. Call the tool again with valid JSON."}
                messages.append({"role": "tool", "tool_call_id": t.id, "content": json.dumps(result)})
            if self.plan and (self.update or self.readme):
                break
        if not self.plan:
            raise AgentError("The AI did not return a valid plan. Try again.")
        return self.plan.model_copy(update={
            "repo_name": self.repo_name, "visibility": self.visibility,
            "description": self.description or self.plan.description,
            "readme": "" if self.update else (self.readme or f"# {self.repo_name}\n\n{self.description}\n"),
            "warnings": self.plan.warnings + ([f"{len(self.blocked)} sensitive file(s) were excluded from the push."] if self.blocked else [])})
