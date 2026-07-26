# SwiperNoSwiping — server configuration
# Single source of truth for all config values.
# Change model strings and thresholds here, nowhere else.

import os

DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
MAX_TURNS = int(os.environ.get("MAX_TURNS", "3"))
APPROVE_THRESHOLD = int(os.environ.get("APPROVE_THRESHOLD", "70"))
LLM_TIMEOUT_S = int(os.environ.get("LLM_TIMEOUT_S", "8"))
