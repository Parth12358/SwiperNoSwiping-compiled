# PRD-C — Backend & DeepSeek LLM

**Owner:** C
**Timebox:** 3 hours, parallel slice
**Status:** Independent. Build against D's stub functions. Fixtures replace A and B until integration.

---

## 1. What you build

The only thing in the project that talks to an AI: `POST /api/interrogate`, backed by `deepseek-v4-flash` via a single `llm.py::complete()` chokepoint. You receive product context + user message, inject the user's profile and purchase history (from D's stubs), construct the interrogator system prompt, call DeepSeek, and return verdict JSON in one round-trip per turn. A valid `DEEPSEEK_API_KEY` is required — the entire extension is inactive without it.

**One-liner for your slice:** "Ask, score, approve or deny. One call, one JSON blob, under 5 seconds."

---

## 2. API-key requirement — the gate

The `DEEPSEEK_API_KEY` in `server/.env` is the single gate that activates the entire extension. Without it:

- The backend starts but `llm.py` returns fail-open verdicts (`{"verdict":"approved","reply":"API key missing. Enjoy your thing.","score":null}`) on every call.
- The extension remains functional (overlay + modal + DB), but every interrogation approves instantly — purchase always goes through.
- **You must validate the key on startup** by curling `deepseek-v4-flash` and confirming a 200. A 401 (bad key) or 400 (bad model name) must be surfaced loudly in the server logs and demo prep checklist.
- The key is server-side only. No other person holds it. It is never committed, never in the extension bundle, never in a fixture file.

### Key validation at startup

```python
# In config.py or main.py startup
async def validate_key():
    try:
        client = openai.AsyncOpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url=config.BASE_URL)
        r = await client.chat.completions.create(
            model=config.DEEPSEEK_MODEL,
            messages=[{"role":"user","content":"ping"}],
            max_tokens=1, timeout=10
        )
        print(f"[startup] DeepSeek key valid, model={config.DEEPSEEK_MODEL}, status=200")
    except Exception as e:
        print(f"[startup] DEEPSEEK_API_KEY INVALID or model error: {e}")
        print("[startup] Server running in fail-open mode. All interrogations will approve.")
```

The key check fails fast and loud. Nobody discovers the key is bad at T+2:50 during rehearsal.

---

## 3. Deliverables

| # | Deliverable | Done when |
|---|-------------|-----------|
| 1 | `config.py` with pinned model string (`deepseek-v4-flash`), base URL, max_turns, approve threshold, all env-var defaults | single source of truth, nowhere else defines these |
| 2 | `llm.py::complete()` — the ONLY function in the project that calls an AI. DeepSeek via `openai` SDK pointed at DeepSeek base URL. | works with `MOCK_LLM=1` (returns canned) and with real key |
| 3 | JSON-mode wiring: prompt contains literal word "json" + worked example, `max_tokens=300`, empty-content guard with retry | valid JSON on every response, never `json.loads("")` |
| 4 | Fail-open: empty content → one retry → `{"verdict":"approved","reply":"..."}` . Timeout >8s → fail open. 401/400 → fail open. | broken backend never blocks a page |
| 5 | `prompts.py` — interrogator persona, 0-39/40-69/70-100 scoring rubric, hard-approve rule for medical/food/safety/work-required | prompt produces grounded, adversarial, two-sentence replies |
| 6 | `POST /api/interrogate` — receives product + user message, injects profile + history from D's `get_context()`, returns verdict JSON | curl a product → get a question → answer it → get a verdict |
| 7 | `main.py` — FastAPI app, `/api/interrogate`, `/api/stats/1`, `/api/profile/1` routes, CORS wildcard (localhost only) | all endpoints return correct shapes |
| 8 | Session state: module-level dict keyed by `session_id`, storing conversation history (max 3 turns) | sessions survive between requests, vanish on server restart |
| 9 | Ship `fixtures/interrogate/turn1.json`, `turn2.json`, `approved.json`, `denied.json` by T+0:20 | B is unblocked |
| 10 | P1: Category classification and history roast line folded into the single DeepSeek call | no second API request |

---

## 4. Contracts — your frozen seams

### 4.1 What B sends to you (HTTP)

```jsonc
// POST /api/interrogate
{
  "user_id": 1,
  "product": {
    "title": "Sony WH-1000XM5",
    "price_cents": 34800,
    "currency": "USD",
    "url": "https://...",
    "image_url": "https://...",
    "site": "amazon",
    "dom_snippet": "…max 4000 chars…"
  },
  "session_id": null,       // null on first turn, your returned value on subsequent turns
  "message": null           // null on first turn, user's justification text after
}
```

### 4.2 What you return to B

```jsonc
// 200
{
  "session_id": "b1f3a9…",
  "verdict": "pending",     // "pending" | "approved" | "denied"
  "reply": "You already own two pairs of over-ears. What changed?",
  "turn": 1,
  "turns_remaining": 2,
  "score": null,            // 0-100 once verdict is final, null while pending
  "savings_total_cents": 128400
}
```

### 4.3 What you call from D

```python
from db import get_context, start_purchase, log_turn, finalize, stats as db_stats

# At start of each new interrogation:
ctx = get_context(user_id)          # → { profile: {...}, recent: [...] }
purchase_id = start_purchase(user_id, product)  # → int

# On every turn:
log_turn(purchase_id, turn_number, "assistant", reply)
log_turn(purchase_id, turn_number, "user", message)

# On final verdict:
finalize(purchase_id, verdict, score, justification)

# For savings counter:
db_stats(user_id)                   # → { denied_count, approved_count, saved_cents, top_category }
```

### 4.4 Field names frozen at T+0:20

`session_id`, `verdict`, `reply`, `turn`, `turns_remaining`, `score`, `savings_total_cents`. Do not rename.

---

## 5. File ownership — only these files

```
server/
  main.py         — FastAPI app, routes, session dict
  llm.py          — complete(): DeepSeek client, JSON mode, retry, empty-content guard, fail-open
  prompts.py      — system prompt, scoring rubric string, hard-approve rule
  config.py       — DEEPSEEK_MODEL, BASE_URL, MAX_TURNS, APPROVE_THRESHOLD, LLM_TIMEOUT_S, env defaults
```

Nobody else edits `server/main.py`, `server/llm.py`, `server/prompts.py`, or `server/config.py`. You don't touch `server/db.py`, `server/schema.sql`, `server/stats.py`, or `seed.py` — those are D's. You import D's stubs, you never open `db.py`.

---

## 6. `llm.py` spec — the single AI chokepoint

**This is the only file in the project that makes an AI call.** No AI call ever originates in the extension. The API key never enters a browser context.

```python
import os
from openai import AsyncOpenAI
import config

_client = None

def _get_client():
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=os.environ["DEEPSEEK_API_KEY"],
            base_url=config.DEEPSEEK_BASE_URL
        )
    return _client

async def complete(messages, response_format={"type": "json_object"}, max_tokens=300, temperature=0.8, timeout=8):
    """Single chokepoint for all AI calls. DeepSeek only."""
    if os.environ.get("MOCK_LLM", "0") == "1":
        return _mock_complete(messages)

    try:
        resp = await asyncio.wait_for(
            _get_client().chat.completions.create(
                model=config.DEEPSEEK_MODEL,
                messages=messages,
                response_format=response_format,
                max_tokens=max_tokens,
                temperature=temperature
            ),
            timeout=timeout
        )
        content = resp.choices[0].message.content

        if not content or content.strip() == "":
            # Empty content is a documented DeepSeek JSON-mode behavior.
            # One retry, then fail open.
            raise ValueError("Empty content from DeepSeek")

        return json.loads(content)

    except Exception as e:
        # Fail open on any error: timeout, 400, 401, empty content, invalid JSON
        print(f"[llm] DeepSeek error: {e}. Failing open.")
        return {
            "verdict": "approved",
            "reply": "Backend's down. Enjoy your thing.",
            "score": None,
            "category": None,
            "roast": None
        }
```

### Configuration — `config.py`

```python
import os

DEEPSEEK_MODEL    = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
MAX_TURNS         = int(os.environ.get("MAX_TURNS", "3"))
APPROVE_THRESHOLD = int(os.environ.get("APPROVE_THRESHOLD", "70"))
LLM_TIMEOUT_S     = int(os.environ.get("LLM_TIMEOUT_S", "8"))
```

**`deepseek-v4-flash` pinned here, nowhere else.** If someone wants to try `deepseek-v4-pro` for harder verdicts, they change this one line.

---

## 7. JSON mode — three gotchas, handle now

DeepSeek's structured output has sharp edges. All three are handled in `llm.py` from the start.

### 7.1 The word "json" must literally appear in the prompt

Setting `response_format: {"type": "json_object"}` is not sufficient. The system or user prompt MUST contain the literal string `json` and a worked example of the target output shape.

```python
# In prompts.py — part of the system prompt:
"""
Respond ONLY with a JSON object. No markdown, no preamble.
Example: {"verdict": "pending", "score": null, "reply": "Why do you need this?", "category": "electronics", "roast": null}
"""
```

### 7.2 Set `max_tokens` deliberately

A truncated response is invalid JSON. Our replies are two sentences — `max_tokens=300` is plenty. It also caps latency. Pinned in `llm.py::complete()` default.

### 7.3 Empty content → retry, never crash

DeepSeek's JSON mode occasionally returns `content: ""` (documented). `llm.py` treats empty content as a failure → one retry → fail open. Never let an empty string reach `json.loads()` and surface as a 500.

```python
if not content or content.strip() == "":
    # One retry
    content = await _retry_complete(messages)  # second attempt
    if not content or content.strip() == "":
        return fail_open_response()
```

---

## 8. `prompts.py` — the interrogator

### Persona

A skeptical but fair friend who's seen your bank statement. Never lectures. Never more than two sentences. Never preachy. Feels like a group chat, not a bank manager.

### System prompt (abridged — see `prompts.py` for full)

```
You are a skeptical but fair friend helping the user avoid impulse purchases.
Keep every reply under two sentences. Never lecture. Be direct, kind, and a little sarcastic.

USER PROFILE: {profile_json}
RECENT PURCHASES: {recent_json}

SCORING RUBRIC (return as JSON):
  0-39  → DENIED. Vague want, "I deserve it", contradicts savings goal, no concrete reason.
  40-69 → PENDING. Ask one more question. Weak but not dishonest. Max 3 turns total, then round down to denied.
  70-100 → APPROVED. Concrete need, replacement for broken item, already budgeted, time-bound external cause.

HARD RULE: If the item is plausibly medical, food, safety equipment, or required for work → APPROVE IMMEDIATELY, skip remaining turns.

Respond ONLY with JSON. Example:
{"verdict":"pending","score":null,"reply":"Your goal is a Japan trip and you're $2,700 short. Try again.","category":"electronics","roast":null}
```

### Prompt injection

Before every call, inject two things from D's `get_context(user_id)`:

1. **Profile:** `{display_name, income_band, monthly_budget_cents, savings_goal, goal_target_cents, known_weakness}`
2. **Recent purchases:** Last 5 rows from `purchases` table (title, price_cents, verdict, created_at)

This is what makes the LLM personal. Wire it before you polish the prompt.

---

## 9. `/api/interrogate` endpoint logic

```python
sessions = {}  # keyed by session_id

@app.post("/api/interrogate")
async def interrogate(req: InterrogateRequest):
    if req.session_id and req.session_id in sessions:
        session = sessions[req.session_id]
    else:
        session = new_session(req.user_id, req.product)

    if req.message:
        session["history"].append({"role": "user", "content": req.message})

    messages = build_messages(session)
    result = await llm.complete(messages)  # one call, returns full JSON

    session["turn"] += 1
    session["history"].append({"role": "assistant", "content": result["reply"]})

    # Log to DB (D's function)
    db.log_turn(session["purchase_id"], session["turn"], "assistant", result["reply"])
    if req.message:
        db.log_turn(session["purchase_id"], session["turn"] - 1, "user", req.message)

    if result["verdict"] in ("approved", "denied"):
        db.finalize(session["purchase_id"], result["verdict"], result.get("score"), session["history"][-2]["content"])
        del sessions[req.session_id]  # clean up

    savings = db.stats(req.user_id)
    return {
        "session_id": session["id"],
        "verdict": result["verdict"],
        "reply": result["reply"],
        "turn": session["turn"],
        "turns_remaining": config.MAX_TURNS - session["turn"],
        "score": result.get("score"),
        "savings_total_cents": savings["saved_cents"]
    }
```

### Turn limit enforcement

- Turn 3 (final): the prompt instructs DeepSeek to give a final verdict. No "pending" allowed past turn 3.
- If DeepSeek still returns `"verdict":"pending"` on turn 3, the backend rounds down to `"denied"`.
- Session state is a dict. Server restart → all sessions vanish (acceptable for demo).

---

## 10. Mock strategy — build without A, B, D

| Flag | Where | Effect |
|------|-------|--------|
| `MOCK_LLM=1` | `server/.env` | `llm.py::complete()` returns canned verdicts. Zero DeepSeek calls, zero latency, zero spend. Default for everyone except you until M2. |
| `MOCK_DB=1` | `server/.env` | D's `db.py` returns hardcoded dicts. You can build the full endpoint before the schema exists. |

### You deliver fixtures to B by T+0:20

```
fixtures/interrogate/
  turn1.json       → { verdict: "pending", reply: "Why do you need this?", turn: 1, turns_remaining: 2, score: null, savings_total_cents: 128400 }
  turn2.json       → { verdict: "pending", reply: "That's weak. Try again.", turn: 2, turns_remaining: 1, score: null, savings_total_cents: 128400 }
  approved.json    → { verdict: "approved", reply: "Fair enough. Go ahead.", turn: 2, turns_remaining: 0, score: 82, savings_total_cents: 128400 }
  denied.json      → { verdict: "denied", reply: "Denied. Your Japan trip is $2,700 short.", turn: 2, turns_remaining: 0, score: 28, savings_total_cents: 163200 }
```

These are **hand-written** — not generated from a live DeepSeek call. They must match the response contract exactly.

---

## 11. Timeline

| Time | Action |
|------|--------|
| **0:00–0:15** | Repo setup, venv, `pip install`, `DEEPSEEK_API_KEY` in `.env`. **Curl `deepseek-v4-flash` and confirm a 200 before writing anything else.** Grep whole repo for `deepseek-chat` and destroy all instances. |
| **0:15–0:20** | **CONTRACT FREEZE.** Read all field names aloud with A, B, D. Agree. |
| **0:20** | **Ship `fixtures/interrogate/*` (4 JSON files).** B is unblocked. |
| **0:20–0:45** | `config.py` → `llm.py` (client, retry, empty-content guard, `MOCK_LLM` mode). `prompts.py` first draft. `main.py` skeleton with `/api/interrogate` route. Work against `MOCK_DB=1` so D's stubs are sufficient. |
| **0:45** | M1 runs (A+B). You keep building — unaffected. |
| **0:45–1:15** | Wire real `deepseek-v4-flash` call (`MOCK_LLM=0`). Tune JSON mode. Test with a `curl` of a fake product → get a grounded question → answer it → get a scored verdict. |
| **1:15** | **M2 merge with D.** D's real `db.py` replaces `MOCK_DB`. Test full write-through path. |
| **1:15–1:45** | Inject profile + purchase history into prompt. Verify personalization with D's seeded data. Tune prompt for snappy, two-sentence replies. |
| **1:45** | **M3 — full end-to-end.** All four together. B points at your live endpoint. |
| **1:45–2:15** | Fix integration: verify `product` pass-through, confirm session IDs echo correctly, tune prompt against real seeded history from D. |
| **2:15** | **FEATURE FREEZE.** Bug fixes only. |
| **2:15–2:45** | Rehearsal 1. If prompt is too soft or too harsh, tune `APPROVE_THRESHOLD` (not the prompt text). |
| **2:45–3:00** | Rehearsal 2. Commit. Stop. |

---

## 12. Success criteria — done when

1. `curl -X POST localhost:8000/api/interrogate -d '{...}'` with a product object returns valid JSON matching the response contract. Before T+0:45 with `MOCK_LLM=1`, by T+1:15 with real DeepSeek.
2. `deepseek-v4-flash` returns a 200 from a direct `curl` in your first 15 minutes.
3. `grep -r "deepseek-chat\|deepseek-reasoner" server/` returns nothing. Ever.
4. The word "json" plus a worked example appear in the system prompt.
5. Empty DeepSeek responses do not crash the server (one retry, then fail open).
6. Three-turn conversation: question → answer → probe → answer → verdict is final. No pending after turn 3.
7. Prompt produces different questions based on seeded history (a user with 4 headphone purchases gets called out on it).
8. Medical/food/safety/work items are approved immediately.
9. `MOCK_LLM=1` works: zero DeepSeek calls, zero latency, valid response shapes.
10. Server prints a loud startup message if `DEEPSEEK_API_KEY` is missing or invalid, and fails open on all requests.

---

## 13. Rules you must not break

1. **One AI client, one chokepoint.** `llm.py::complete()` is the only function that calls an AI. No other file constructs an AI request. No OpenAI, no Anthropic, no fallback provider. DeepSeek only.
2. **One call per turn.** Reply + verdict + score + category + roast in one JSON object. Do not chain four sequential calls.
3. **Model string pinned in `config.py`.** Not in `prompts.py`, not in `main.py`, not in an environment variable default spread across four files. One place.
4. **`deepseek-v4-flash`, not `deepseek-chat`.** The alias is deprecated as of 2026-07-24 and returns 400s. Grep before every merge.
5. **Thinking mode off.** Not a model — a parameter. Leave it off. The 8s timeout is non-negotiable for a demo where the user is watching a spinner.
6. **Fail open.** 5xx, 4xx, timeout, empty content, invalid JSON → `{"verdict":"approved","reply":"…"}`. Never a 500.
7. **Only edit your own files.** Import D's stubs. Never open `db.py`. Ask A/B for cross-directory changes.
8. **No DeepSeek key in the extension.** The key lives in `server/.env` and is only read by `server/llm.py`. Content scripts use the background service worker proxy.
