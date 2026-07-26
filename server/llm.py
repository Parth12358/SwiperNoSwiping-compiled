# SwiperNoSwiping — DeepSeek LLM client
# Single chokepoint for all AI calls. No other file constructs an AI request.
# Handles empty content, retries, fail-open, and MOCK_LLM mode.

import asyncio
import json
import os
from openai import AsyncOpenAI
import config

_client = None

def _get_client():
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=os.environ["DEEPSEEK_API_KEY"],
            base_url=config.DEEPSEEK_BASE_URL,
        )
    return _client

async def complete(messages, response_format=None, max_tokens=300, temperature=0.8, timeout=None):
    if os.environ.get("MOCK_LLM", "0") == "1":
        return _mock_complete(messages)

    timeout_s = timeout or config.LLM_TIMEOUT_S
    fmt = response_format or {"type": "json_object"}

    try:
        resp = await asyncio.wait_for(
            _get_client().chat.completions.create(
                model=config.DEEPSEEK_MODEL,
                messages=messages,
                response_format=fmt,
                max_tokens=max_tokens,
                temperature=temperature,
            ),
            timeout=timeout_s,
        )
        content = resp.choices[0].message.content

        if not content or content.strip() == "":
            raise ValueError("Empty content from DeepSeek")

        return json.loads(content)

    except (json.JSONDecodeError, ValueError):
        try:
            resp = await asyncio.wait_for(
                _get_client().chat.completions.create(
                    model=config.DEEPSEEK_MODEL,
                    messages=messages,
                    response_format=fmt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                ),
                timeout=timeout_s,
            )
            content = resp.choices[0].message.content
            if not content or content.strip() == "":
                raise ValueError("Empty content from DeepSeek (retry)")
            return json.loads(content)
        except Exception:
            return _fail_open()

    except Exception:
        return _fail_open()

def _fail_open():
    return {
        "verdict": "approved",
        "score": None,
        "reply": "Backend's down. Enjoy your thing.",
        "category": None,
        "roast": None,
    }

def _mock_complete(messages):
    last = messages[-1]["content"] if messages else ""
    if "broken" in last.lower() or "need" in last.lower() or "work" in last.lower():
        return {"verdict": "approved", "score": 78, "reply": "Fair enough. Go ahead.", "category": "electronics", "roast": None}
    if not last or last == "null":
        return {"verdict": "pending", "score": None, "reply": "You already own two pairs of over-ears. What changed?", "category": "electronics", "roast": None}
    return {"verdict": "denied", "score": 28, "reply": "Denied. Your Japan trip is $2,700 short.", "category": "electronics", "roast": None}
