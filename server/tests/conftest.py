import os
import sys

# Tests import the server modules directly (import llm, main, ...).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Safety net: no test hits DeepSeek unless it explicitly opts in.
# Must be set before config.py runs load_dotenv (override=False → env wins).
os.environ.setdefault("MOCK_LLM", "1")
