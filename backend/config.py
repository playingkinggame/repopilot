import os

from dotenv import load_dotenv

load_dotenv()


def _int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, default))
    except ValueError:
        return default


GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL") or "openai/gpt-oss-120b"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
DATABASE_URL = os.getenv("DATABASE_URL") or "sqlite:///./repopilot.db"
FRONTEND_URL = os.getenv("FRONTEND_URL") or "http://localhost:5173"
MAX_AGENT_TOOL_CALLS = _int("MAX_AGENT_TOOL_CALLS", 10)
MAX_FILE_SIZE_MB = _int("MAX_FILE_SIZE_MB", 25)
