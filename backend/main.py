import asyncio
import json
import shutil
import time
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from . import config, events, github_service, gitops
from .agent import Agent, AgentError
from .db import Job, SessionLocal
from .scanner import resolve_folder, scan as scan_folder
from .schemas import META_FILES, ApproveIn, JobCreate, Plan, validate_plan

app = FastAPI(title="RepoPilot")
app.add_middleware(CORSMiddleware, allow_origins=[config.FRONTEND_URL, "http://127.0.0.1:5173", "http://localhost:5173"],
                   allow_methods=["*"], allow_headers=["*"])
_scans: dict[str, dict] = {}


def get_db():
    with SessionLocal() as db:
        yield db


def need(db: Session, job_id: str) -> Job:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    return job


def get_scan(job_id: str, folder: str) -> dict:
    if job_id not in _scans:
        _scans[job_id] = scan_folder(Path(folder))
    return _scans[job_id]


def sets(s: dict) -> tuple[set[str], set[str]]:
    return {f["path"] for f in s["files"]}, {b["path"] for b in s["blocked"]}


def iso(d: datetime | None) -> str | None:
    return d.isoformat() + "Z" if d else None


def job_out(job: Job, detail: bool = False) -> dict:
    d = {"id": job.id, "folder": job.folder, "repo_name": job.repo_name, "description": job.description or "",
         "visibility": job.visibility, "status": job.status, "commits": job.commits or 0, "created_at": iso(job.created_at),
         "completed_at": iso(job.completed_at), "github_url": job.github_url, "error": job.error}
    if detail:
        try:
            s = get_scan(job.id, job.folder)
        except OSError:
            s = {"files": [], "blocked": [], "findings": []}
        d["plan"] = json.loads(job.plan_json) if job.plan_json else None
        d["security"] = {"blocked": s["blocked"], "findings": s["findings"]}
        d["available_files"] = sorted(f["path"] for f in s["files"] if f["path"] not in META_FILES)
    return d


def set_job(job_id: str, **kw) -> None:
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        for k, v in kw.items():
            setattr(job, k, v)
        db.commit()


def fail(phase: str, job_id: str, msg: str) -> None:
    set_job(job_id, status="FAILED", error=msg, completed_at=datetime.utcnow())
    events.emit(job_id, phase, "failed", msg)


@app.get("/api/health")
def health():
    return {"status": "ok", "git_installed": shutil.which("git") is not None}


@app.get("/api/settings")
def settings():
    return {"groq_model": config.GROQ_MODEL, "max_agent_tool_calls": config.MAX_AGENT_TOOL_CALLS,
            "max_file_size_mb": config.MAX_FILE_SIZE_MB, "groq_configured": bool(config.GROQ_API_KEY),
            "github_configured": bool(config.GITHUB_TOKEN)}


@app.post("/api/jobs", status_code=201)
def create_job(body: JobCreate, db: Session = Depends(get_db)):
    try:
        folder = resolve_folder(body.folder)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    job = Job(id=uuid.uuid4().hex[:12], folder=str(folder), repo_name=body.repo_name, description=body.description,
              visibility=body.visibility, status="CREATED")
    db.add(job)
    db.commit()
    return job_out(job)


@app.get("/api/jobs")
def list_jobs(db: Session = Depends(get_db)):
    return [job_out(j) for j in db.query(Job).order_by(Job.created_at.desc()).limit(200)]


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db)):
    return job_out(need(db, job_id), detail=True)


@app.post("/api/jobs/{job_id}/scan")
def scan_job(job_id: str, db: Session = Depends(get_db)):
    job = need(db, job_id)
    if job.status in ("PLANNING", "APPROVED", "PUSHING", "COMPLETED"):
        raise HTTPException(409, f"Cannot scan a job in state {job.status}.")
    events.clear(job_id, "plan")
    job.status = "SCANNING"
    db.commit()
    events.emit(job_id, "plan", "log", "Scanning folder")
    try:
        s = scan_folder(Path(job.folder))
    except OSError:
        job.status, job.error = "FAILED", "The folder could not be read."
        db.commit()
        raise HTTPException(400, job.error) from None
    _scans[job_id] = s
    events.emit(job_id, "plan", "log", f"Security scan: {len(s['blocked'])} sensitive file(s) excluded, {len(s['files'])} safe file(s) found")
    job.status = "CREATED" if s["files"] else "BLOCKED"
    job.error = None if s["files"] else "No pushable files were found in this folder."
    db.commit()
    return job_out(job, detail=True)


def run_plan(job_id: str) -> None:
    try:
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            folder, name, desc, vis = job.folder, job.repo_name, job.description or "", job.visibility
        plan = Agent(get_scan(job_id, folder), name, desc, vis, lambda m: events.emit(job_id, "plan", "log", m)).run()
        set_job(job_id, status="REVIEW", plan_json=plan.model_dump_json(), commits=len(plan.commits), error=None)
        events.emit(job_id, "plan", "plan_ready", "Plan ready for review")
    except AgentError as e:
        fail("plan", job_id, str(e))
    except Exception:
        fail("plan", job_id, "Unexpected error while generating the plan.")


@app.post("/api/jobs/{job_id}/plan", status_code=202)
def plan_job(job_id: str, bg: BackgroundTasks, db: Session = Depends(get_db)):
    job = need(db, job_id)
    if job.status not in ("CREATED", "REVIEW", "FAILED"):
        raise HTTPException(409, f"Cannot plan a job in state {job.status}.")
    if not config.GROQ_API_KEY:
        raise HTTPException(400, "GROQ_API_KEY is not configured on the backend.")
    if job_id not in _scans:
        raise HTTPException(409, "Scan the folder first.")
    if job.status != "CREATED":
        events.clear(job_id, "plan")
    job.status, job.error = "PLANNING", None
    db.commit()
    bg.add_task(run_plan, job_id)
    return job_out(job)


@app.put("/api/jobs/{job_id}/plan")
def put_plan(job_id: str, plan: Plan, db: Session = Depends(get_db)):
    job = need(db, job_id)
    if job.status != "REVIEW":
        raise HTTPException(409, "The plan can only be edited during review.")
    allowed, blocked = sets(get_scan(job_id, job.folder))
    try:
        plan = validate_plan(plan, allowed, blocked)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    job.plan_json, job.commits = plan.model_dump_json(), len(plan.commits)
    job.repo_name, job.description, job.visibility = plan.repo_name, plan.description, plan.visibility
    db.commit()
    return job_out(job, detail=True)


@app.post("/api/jobs/{job_id}/approve")
def approve_job(job_id: str, body: ApproveIn, db: Session = Depends(get_db)):
    job = need(db, job_id)
    if job.status != "REVIEW" or not job.plan_json:
        raise HTTPException(409, "There is no plan waiting for approval.")
    if get_scan(job_id, job.folder)["blocked"] and not body.acknowledge_warnings:
        raise HTTPException(400, "Acknowledge the security warning before approving.")
    events.clear(job_id, "push")
    job.status = "APPROVED"
    db.commit()
    events.emit(job_id, "push", "log", "Plan approved")
    return job_out(job)


def run_push(job_id: str) -> None:
    def log(m: str) -> None:
        events.emit(job_id, "push", "log", m)

    try:
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            plan, folder_raw = Plan.model_validate_json(job.plan_json), job.folder
        log("Validating folder")
        folder = resolve_folder(folder_raw)
        s = scan_folder(folder)
        _scans[job_id] = s
        allowed, blocked = sets(s)
        plan = validate_plan(plan, allowed, blocked)
        gitops.check_git()
        gitops.init_repo(folder)
        log("Git initialized")
        meta = gitops.write_meta(folder, plan, blocked)
        groups = [(c.message, c.files) for c in plan.commits]
        if meta:
            groups.append(("docs: add README, .gitignore and license", meta))
        made = 0
        for i, (msg, files) in enumerate(groups, 1):
            log(f"Creating commit {i}/{len(groups)}: {msg}")
            made += gitops.commit(folder, msg, files)
        log("Creating GitHub repository")
        try:
            url, clone = github_service.create_repo(plan.repo_name, plan.description, plan.visibility == "private", plan.topics)
        except github_service.GitHubError as e:
            raise github_service.GitHubError(f"{e} Local commits were preserved.") from None
        log("Pushing repository")
        gitops.push(folder, clone)
        set_job(job_id, status="COMPLETED", github_url=url, commits=made, completed_at=datetime.utcnow(), error=None)
        events.emit(job_id, "push", "completed", url)
    except (gitops.GitError, github_service.GitHubError, ValueError) as e:
        fail("push", job_id, str(e))
    except Exception:
        fail("push", job_id, "Unexpected error while pushing. Your project files were not deleted.")


@app.post("/api/jobs/{job_id}/push", status_code=202)
def push_job(job_id: str, bg: BackgroundTasks, db: Session = Depends(get_db)):
    job = need(db, job_id)
    if job.status != "APPROVED":
        raise HTTPException(409, "Approve the plan before pushing.")
    if not config.GITHUB_TOKEN:
        raise HTTPException(400, "GITHUB_TOKEN is not configured on the backend.")
    job.status = "PUSHING"
    db.commit()
    bg.add_task(run_push, job_id)
    return job_out(job)


TERMINAL = {"plan_ready", "completed", "failed"}
SYNTHETIC = {("plan", "REVIEW"): "plan_ready", ("plan", "APPROVED"): "plan_ready", ("plan", "PUSHING"): "plan_ready",
             ("plan", "COMPLETED"): "plan_ready", ("plan", "FAILED"): "failed", ("push", "COMPLETED"): "completed",
             ("push", "FAILED"): "failed"}


@app.get("/api/jobs/{job_id}/events")
async def job_events(job_id: str, request: Request, phase: str = "plan"):
    with SessionLocal() as db:
        need(db, job_id)
    try:
        start = int(request.headers.get("last-event-id", "-1")) + 1
    except ValueError:
        start = 0

    async def gen():
        idx, last_ping = start, time.time()
        while not await request.is_disconnected():
            batch = events.since(job_id, idx)
            for i, e in batch:
                idx = i + 1
                if e["phase"] == phase:
                    yield f"id: {i}\ndata: {json.dumps(e)}\n\n"
                    if e["type"] in TERMINAL:
                        return
            if not batch:
                with SessionLocal() as db:
                    job = db.get(Job, job_id)
                    kind = SYNTHETIC.get((phase, job.status))
                    if kind and job.status not in ("PLANNING", "PUSHING"):
                        msg = job.error or job.github_url or ""
                        yield f"data: {json.dumps({'phase': phase, 'type': kind, 'message': msg})}\n\n"
                        return
                if time.time() - last_ping > 10:
                    last_ping = time.time()
                    yield ": ping\n\n"
            await asyncio.sleep(0.4)

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
