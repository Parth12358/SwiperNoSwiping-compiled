"""OWNER: C. Single source of truth for all backend settings.

The DeepSeek model string is pinned HERE and nowhere else (PRD-C §6, rule 3).
deepseek-v4-flash only — the old chat/reasoner aliases died 2026-07-24 and return
400s, so anything a tutorial suggests is wrong. Do not add model strings elsewhere.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# D's db.py resolves its DB path from env at import time with a cwd-relative
# default; pin it to the repo's seeded db so `uvicorn main:app` works from any
# directory. config is imported before db in main.py, so this lands in time.
os.environ.setdefault("SWIPERNO_DB_PATH", str(Path(__file__).parent / "swiperno.db"))

DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
MAX_TURNS = int(os.environ.get("MAX_TURNS", "3"))
APPROVE_THRESHOLD = int(os.environ.get("APPROVE_THRESHOLD", "70"))
LLM_TIMEOUT_S = int(os.environ.get("LLM_TIMEOUT_S", "8"))
