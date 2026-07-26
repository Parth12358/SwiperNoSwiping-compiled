"""OWNER: C. The single AI chokepoint (PRD-C §6).

This is the ONLY file in the project that talks to an AI. DeepSeek only — no
second provider, no fallback provider (PRD §7.1, N7). Everything here fails
open: any error returns an approved verdict so a broken backend never traps
anyone on a checkout page.

Sharp edges handled here (PRD-C §7):
  1. The literal word "json" + a worked example live in the prompt (prompts.py).
  2. max_tokens is always set — a truncated response is invalid JSON.
  3. Empty content is a documented DeepSeek JSON-mode behavior → one retry,
     then fail open. An empty string never reaches json.loads().

v4 models think BY DEFAULT (verified live: reasoning_content comes back on a
bare request). Thinking mode off therefore means explicitly sending
{"thinking": {"type": "disabled"}} — otherwise reasoning burns the 8s budget.
"""

import asyncio
import json
import os

from openai import AsyncOpenAI

import config

_client = None

# Requests where thinking is off get plain content; keep it that way (PRD §7.1).
_THINKING_OFF = {"thinking": {"type": "disabled"}}


def _get_client():
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=os.environ["DEEPSEEK_API_KEY"],
            base_url=config.DEEPSEEK_BASE_URL,
        )
    return _client


def fail_open_response():
    """The verdict returned on ANY failure. Approve and get out of the way."""
    return {
        "verdict": "approved",
        "reply": "Backend's down. Enjoy your thing.",
        "score": None,
        "category": None,
        "roast": None,
    }


async def _call(messages, response_format, max_tokens, temperature, timeout):
    resp = await asyncio.wait_for(
        _get_client().chat.completions.create(
            model=config.DEEPSEEK_MODEL,
            messages=messages,
            response_format=response_format,
            max_tokens=max_tokens,
            temperature=temperature,
            extra_body=_THINKING_OFF,
        ),
        timeout=timeout,
    )
    return resp.choices[0].message.content


async def complete(
    messages,
    response_format=None,
    max_tokens=300,
    temperature=0.8,
    timeout=None,
):
    """One call per interrogation turn: reply + verdict + score + category +
    roast in a single JSON object. Never raises — always returns a dict."""
    if os.environ.get("MOCK_LLM", "0") == "1":
        return _mock_complete(messages)

    response_format = response_format or {"type": "json_object"}
    timeout = timeout if timeout is not None else config.LLM_TIMEOUT_S

    # Attempt 1 + one retry, but ONLY for empty/invalid content (§7.3).
    # Timeouts and API errors fail open immediately — a retry there doubles
    # worst-case latency past the 8s budget while the user watches a spinner.
    for attempt in (1, 2):
        try:
            content = await _call(messages, response_format, max_tokens, temperature, timeout)
        except Exception as e:
            print(f"[llm] DeepSeek error: {e!r}. Failing open.")
            return fail_open_response()

        if not content or not content.strip():
            print(f"[llm] empty content from DeepSeek (attempt {attempt}) — documented JSON-mode behavior.")
            continue
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            print(f"[llm] invalid JSON from DeepSeek (attempt {attempt}): {e}")
            continue

    print("[llm] no valid JSON after retry. Failing open.")
    return fail_open_response()


def _mock_complete(messages):
    """MOCK_LLM=1 — canned verdicts, zero DeepSeek calls, zero latency, zero
    spend. Shape-identical to the real thing so B/D can build without a key."""
    users = [m for m in messages if m["role"] == "user"]
    last = users[-1]["content"].lower() if users else ""
    assistant_turns = sum(1 for m in messages if m["role"] == "assistant")

    if last and any(w in last for w in ("broke", "broken", "work", "medical", "doctor", "safety", "food")):
        return {
            "verdict": "approved",
            "score": 82,
            "reply": "Fair enough. Go ahead.",
            "category": "electronics",
            "roast": None,
        }
    if assistant_turns >= config.MAX_TURNS - 1:
        return {
            "verdict": "denied",
            "score": 28,
            "reply": "Denied. Your Japan trip is $2,700 short.",
            "category": "electronics",
            "roast": "Fourth pair of headphones, huh?",
        }
    questions = ["Why do you need this?", "That's weak. Try again."]
    return {
        "verdict": "pending",
        "score": None,
        "reply": questions[min(assistant_turns, len(questions) - 1)],
        "category": "electronics",
        "roast": None,
    }
