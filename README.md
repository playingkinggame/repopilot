# RepoPilot

Local AI-powered GitHub publisher. Point it at a project folder: it scans the files, blocks anything that looks like a secret, has a Groq-hosted agent propose a clean commit history plus README, `.gitignore` and license, lets you edit the plan, and after your approval creates the commits, the GitHub repository, and pushes.

## Architecture
- **backend/** FastAPI + SQLAlchemy (SQLite). `scanner.py` and `sensitive.py` run locally; `agent.py` is a bounded tool-calling loop (`scan_folder`, `scan_for_secrets`, `propose_plan`, `generate_readme`); `gitops.py` and `github_service.py` perform every real action deterministically.
- **frontend/** React + Vite + TypeScript + Tailwind + TanStack Query. Progress arrives over Server-Sent Events at `/api/jobs/{id}/events`.

## Requirements
Windows 11 (any OS works), Python 3.11+, Node 18+, Git, a Groq API key, and a GitHub token with the `repo` scope.

## Setup
```powershell
copy .env.example .env      # then fill in GROQ_API_KEY and GITHUB_TOKEN
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```
In a second terminal:
```powershell
cd frontend
npm install
npm run dev
```
Open http://localhost:5173.

## Usage
New push → enter folder, name, visibility → Generate plan → edit → Approve & push. Job history is under History.

## Security notes
- Files with secrets (`.env`, keys, tokens, credentials, connection strings, high-entropy strings) are excluded before anything reaches the LLM and can never be added back.
- Secret values are never returned, logged, stored, streamed, or sent to Groq; only file names and finding types are.
- The LLM only proposes a plan. It never runs commands; Git is invoked with fixed argument lists, no shell.
- Approval is enforced by backend job state. Approved README, `.gitignore` and LICENSE replace files of the same name (clear a field to keep your own).
- The GitHub token is used for a single push URL and is not saved in the remote configuration.

## Updating an existing repository
Choose **Update existing repo** (auto-selected when the folder is a Git repo with a GitHub `origin`). RepoPilot finds uncommitted changes and commits you already made in VS Code, blocks sensitive files, groups the changes into commits, and after approval pushes to the chosen branch. It first checks GitHub for newer commits and stops if you are behind (pull in VS Code first). It never force-pushes. The folder must be the repository root.
