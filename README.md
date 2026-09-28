# RepoPilot — AI‑Powered Repository Autopilot  

**RepoPilot** automates the creation of a new GitHub repository from a local folder.  
An LLM‑driven planning agent scans the codebase, detects secrets, generates a conventional‑commit plan, builds a `README.md`, `.gitignore`, optional MIT license, and pushes the commits to GitHub—all with a single API call.

---

## Table of Contents  

- [Features](#features)  
- [Tech Stack](#tech-stack)  
- [Quick Start](#quick-start)  
  - [Prerequisites](#prerequisites)  
  - [Backend](#backend-setup)  
  - [Frontend](#frontend-setup)  
- [Configuration](#configuration)  
- [API Overview](#api-overview)  
- [Running Locally (Docker optional)](#running-locally-docker-optional)  
- [Development & Contributing](#development--contributing)  
- [License](#license)  

---

## Features  

- **Full‑stack**: FastAPI backend + React/Vite/Tailwind frontend.  
- **AI planning**: Uses Groq (or compatible OpenAI) model to generate a multi‑commit plan with Conventional Commit messages.  
- **Secret scanning**: Detects hard‑coded credentials before any push.  
- **Automatic repo creation**: Calls GitHub API to create a repo, push commits, and expose the URL.  
- **Live job events**: Frontend receives real‑time logs, plan preview, and status updates via streaming endpoint.  
- **Configurable limits**: Max agent tool calls, max file size, model choice, etc.  

---

## Tech Stack  

| Layer | Technology |
|-------|------------|
| **Backend** | Python 3.11, FastAPI, SQLAlchemy (SQLite), Groq SDK, PyGithub |
| **Frontend** | React 18, TypeScript, Vite, TailwindCSS, TanStack Query |
| **Database** | SQLite (`repopilot.db`) |
| **Package managers** | `pip` (backend), `npm` (frontend) |

---

## Quick Start  

### Prerequisites  

- **Python ≥ 3.10**  
- **Node ≥ 18** (for the frontend)  
- A **GitHub personal access token** with `repo` scope.  
- A **Groq API key** (or any OpenAI‑compatible model key).  

### Backend Setup  

```bash
# Clone the repo
git clone https://github.com/yourusername/repopilot.git
cd repopilot

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt

# Copy example env and fill in your secrets
cp .env.example .env
# Edit .env:
#   GROQ_API_KEY=your-groq-key
#   GITHUB_TOKEN=your-github-token
#   FRONTEND_URL=http://localhost:5173   # keep default for dev
#   DATABASE_URL=sqlite:///./repopilot.db # optional custom DB
```

Run the API:

```bash
uvicorn backend.main:app --reload --port 8000
```

The backend will be available at `http://localhost:8000`.

### Frontend Setup  

```bash
# From the repo root
cd frontend

# Install Node dependencies
npm ci

# Start the dev server
npm run dev
```

The UI will be served at `http://localhost:5173` (CORS is pre‑configured).

Open the page, select a local folder, provide a repository name/description, and let RepoPilot do the rest.

---

## Configuration  

All settings live in `.env` (see `.env.example`):

| Variable | Description |
|----------|-------------|
| `GROQ_API_KEY` | API key for Groq (or compatible OpenAI endpoint). |
| `GROQ_MODEL` | Model name, default `openai/gpt-oss-120b`. |
| `GITHUB_TOKEN` | GitHub PAT with `repo` scope. |
| `DATABASE_URL` | SQLAlchemy connection string; default uses SQLite. |
| `FRONTEND_URL` | URL of the React dev server (CORS whitelist). |
| `MAX_AGENT_TOOL_CALLS` | Upper bound on tool calls the planning agent may make (default 10). |
| `MAX_FILE_SIZE_MB` | Files larger than this are ignored (default 25 MB). |

---

## API Overview  

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/jobs/` | `POST` | Create a new push job (folder, repo name, description, visibility). |
| `/jobs/{job_id}` | `GET` | Retrieve job details (plan, security findings, available files). |
| `/jobs/{job_id}/events` | `GET` (stream) | SSE‑style stream of log events & phase changes. |
| `/jobs/{job_id}/approve` | `POST` | Approve the generated plan and start the push. |
| `/settings` | `GET` | Return current server settings (model, limits, config status). |

The frontend communicates with these endpoints via the helper functions in `frontend/src/api.ts`.

---

## Running Locally (Docker – optional)

A Dockerfile is not shipped, but you can quickly spin up both services with Compose:

```yaml
# docker-compose.yml (example)
services:
  backend:
    image: python:3.11-slim
    working_dir: /app
    volumes:
      - .:/app
    env_file: .env
    command: uvicorn backend.main:app --host 0.0.0.0 --port 8000
    ports: ["8000:8000"]
  frontend:
    image: node:20-alpine
    working_dir: /app/frontend
    volumes:
      - .:/app
    command: npm run dev -- --host
    ports: ["5173:5173"]
```

```bash
docker compose up --build
```

---

## Development & Contributing  

1. **Fork** the repository and create a feature branch.  
2. Follow the **Backend** and **Frontend** setup steps above.  
3. Run tests (if added) with `pytest` for Python and `npm test` for the UI.  
4. Submit a **Pull Request** with a clear description of changes.  

### Code Style  

- Python: `ruff` / `black` (PEP 8 compliant).  
- TypeScript/React: `eslint` + `prettier`.  

---

## License  

RepoPilot does **not** ship a default license file.  
When generating a repository the user can choose `MIT` or `none`.  
The source code of this project is provided **as‑is** without an explicit open‑source license; feel free to adapt it for personal use.  

---  

**Happy automating!** 🎉  



---  

*Generated with the help of RepoPilot itself.*
