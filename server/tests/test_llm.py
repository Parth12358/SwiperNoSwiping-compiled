"""llm.py — the AI chokepoint: fail-open paths, retry semantics, mock mode."""
import asyncio
import json

import pytest

import config
import llm

MSGS = [{"role": "user", "content": "x"}]


@pytest.fixture(autouse=True)
def _reset_client_and_call():
    orig_call = llm._call
    yield
    llm._call = orig_call
    llm._client = None


def _run(coro):
    return asyncio.run(coro)


def test_empty_content_retries_once_then_fails_open(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "0")
    calls = {"n": 0}

    async def empty(*a, **k):
        calls["n"] += 1
        return ""

    llm._call = empty
    r = _run(llm.complete(MSGS))
    assert r["verdict"] == "approved"
    assert r["reply"]
    assert calls["n"] == 2  # attempt + exactly one retry


def test_invalid_json_retries_then_fails_open(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "0")
    calls = {"n": 0}

    async def bad(*a, **k):
        calls["n"] += 1
        return "not json {"

    llm._call = bad
    r = _run(llm.complete(MSGS))
    assert r["verdict"] == "approved"
    assert calls["n"] == 2


def test_timeout_fails_open_immediately_no_retry(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "0")
    calls = {"n": 0}

    async def slow(*a, **k):
        calls["n"] += 1
        raise asyncio.TimeoutError()

    llm._call = slow
    r = _run(llm.complete(MSGS))
    assert r["verdict"] == "approved"
    assert calls["n"] == 1  # retrying a timeout would double worst-case latency


def test_api_error_fails_open(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "0")

    async def boom(*a, **k):
        raise RuntimeError("401 from DeepSeek")

    llm._call = boom
    r = _run(llm.complete(MSGS))
    assert r["verdict"] == "approved"


def test_empty_then_valid_recovers(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "0")
    good = {"verdict": "pending", "score": None, "reply": "Why?", "category": "x", "roast": None}
    seq = iter(["", json.dumps(good)])

    async def flaky(*a, **k):
        return next(seq)

    llm._call = flaky
    assert _run(llm.complete(MSGS)) == good


def test_missing_api_key_fails_open(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "0")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    llm._client = None
    r = _run(llm.complete(MSGS))
    assert r["verdict"] == "approved"


def test_fail_open_response_shape():
    r = llm.fail_open_response()
    assert r["verdict"] == "approved"
    assert {"verdict", "reply", "score", "category", "roast"} <= set(r)
    # Returns a fresh dict each time — callers must not share/mutate one instance.
    assert llm.fail_open_response() is not r


def test_mock_mode_makes_zero_real_calls(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "1")
    calls = {"n": 0}

    async def boom(*a, **k):
        calls["n"] += 1
        raise RuntimeError("real call attempted under MOCK_LLM")

    llm._call = boom
    r = _run(llm.complete(MSGS))
    assert calls["n"] == 0
    assert {"verdict", "reply", "score", "category", "roast"} <= set(r)


def test_mock_progression_pending_pending_denied(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "1")
    sys_msg = {"role": "system", "content": "s"}

    r1 = _run(llm.complete([sys_msg]))
    assert (r1["verdict"], r1["score"]) == ("pending", None)

    history = [sys_msg, {"role": "assistant", "content": r1["reply"]}, {"role": "user", "content": "I want it"}]
    r2 = _run(llm.complete(history))
    assert r2["verdict"] == "pending"

    history += [{"role": "assistant", "content": r2["reply"]}, {"role": "user", "content": "just because"}]
    r3 = _run(llm.complete(history))
    assert r3["verdict"] == "denied"
    assert isinstance(r3["score"], int)


def test_mock_strong_answer_approves(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "1")
    msgs = [
        {"role": "system", "content": "s"},
        {"role": "assistant", "content": "Why?"},
        {"role": "user", "content": "my headphones broke and I need them for work"},
    ]
    r = _run(llm.complete(msgs))
    assert r["verdict"] == "approved"
    assert r["score"] >= config.APPROVE_THRESHOLD
