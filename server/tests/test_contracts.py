"""Repo-level guards: fixture shapes, model pin, hygiene greps, thinking-off."""
import json
from pathlib import Path

import config

SERVER_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = SERVER_DIR.parent
FIXTURES = REPO_DIR / "fixtures" / "interrogate"

FROZEN_FIELDS = {"session_id", "verdict", "reply", "turn", "turns_remaining", "score", "savings_total_cents"}

# Built by concatenation so this file never matches its own grep.
BANNED = ["deepseek-" + "chat", "deepseek-" + "reasoner", "webextension-" + "polyfill"]


def test_model_pin():
    assert config.DEEPSEEK_MODEL == "deepseek-v4-flash"
    assert config.DEEPSEEK_BASE_URL == "https://api.deepseek.com"


def test_config_knobs_sane():
    assert config.MAX_TURNS >= 1
    assert 0 <= config.APPROVE_THRESHOLD <= 100
    assert config.LLM_TIMEOUT_S > 0


def test_fixture_files_match_response_contract():
    names = {"turn1.json", "turn2.json", "approved.json", "denied.json"}
    assert {p.name for p in FIXTURES.glob("*.json")} == names
    for path in sorted(FIXTURES.glob("*.json")):
        body = json.loads(path.read_text())
        assert set(body) == FROZEN_FIELDS, path.name
        assert body["verdict"] in ("pending", "approved", "denied"), path.name
        assert isinstance(body["session_id"], str), path.name
        assert isinstance(body["reply"], str) and body["reply"], path.name
        assert isinstance(body["turn"], int), path.name
        assert isinstance(body["turns_remaining"], int), path.name
        assert body["score"] is None or isinstance(body["score"], int), path.name
        assert isinstance(body["savings_total_cents"], int), path.name


def test_fixture_verdict_score_consistency():
    for path in FIXTURES.glob("*.json"):
        body = json.loads(path.read_text())
        if body["verdict"] == "pending":
            assert body["score"] is None, path.name
        else:
            assert isinstance(body["score"], int), path.name


def test_no_banned_strings_anywhere():
    # PRD §15 hygiene gate: run over server code and fixtures.
    files = [p for p in SERVER_DIR.rglob("*.py") if ".venv" not in p.parts]
    files += list(FIXTURES.glob("*.json"))
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for banned in BANNED:
            assert banned not in text, f"{banned} found in {path}"


def test_thinking_explicitly_disabled_in_llm():
    # v4 models think BY DEFAULT (verified live). Removing this param silently
    # reintroduces reasoning latency + empty-content risk. Keep it pinned.
    text = (SERVER_DIR / "llm.py").read_text()
    assert '"thinking"' in text and '"disabled"' in text


def test_single_ai_chokepoint():
    # llm.py is the ONLY server file that constructs an AI client (PRD rule 1).
    for path in SERVER_DIR.glob("*.py"):
        if path.name == "llm.py":
            continue
        assert "AsyncOpenAI(" not in path.read_text(), path.name
