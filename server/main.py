"""OWNER: C. FastAPI app: /api/interrogate, /api/stats, /api/profile (PRD-C §9).

Run:  cd server && .venv/bin/uvicorn main:app --port 8000

Error contract (PRD §9.5): this server never returns a 500. Any failure
anywhere returns a 200 with an approved fail-open verdict — a broken backend
must never trap anyone on a checkout page.

Session state is a module-level dict (PRD-C deliverable 8). Server restart →
sessions vanish. That is acceptable for the demo.
"""

import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import config
import db
import llm
import prompts
import stats as stats_module

sessions = {}  # keyed by session_id

PROFILE_FIELDS = (
    "display_name",
    "income_band",
    "monthly_budget_cents",
    "savings_goal",
    "goal_target_cents",
    "known_weakness",
)


@asynccontextmanager
async def lifespan(app):
    _init_db()
    await _validate_key()
    yield


app = FastAPI(title="SwipernoSwiping backend", lifespan=lifespan)
app.add_middleware(  # localhost demo only — CORS wide open on purpose
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _init_db():
    try:
        db.init()
        print("[startup] db initialized at", __import__("os").environ.get("SWIPERNO_DB_PATH", "swiperno.db"), flush=True)
    except Exception as e:
        print(f"[startup] db.init failed: {e!r} — continuing; requests fail open on db errors.", flush=True)


async def _validate_key():
    """Fail fast and loud (PRD-C §2). Never blocks startup — fail-open mode."""
    import os

    if os.environ.get("MOCK_LLM", "0") == "1":
        print("[startup] MOCK_LLM=1 — no DeepSeek calls will be made.", flush=True)
        return
    if not os.environ.get("DEEPSEEK_API_KEY"):
        print("[startup] DEEPSEEK_API_KEY MISSING from server/.env.", flush=True)
        print("[startup] Server running in fail-open mode. ALL interrogations will approve.", flush=True)
        return
    try:
        import asyncio

        # Validate AND pre-warm the exact production path (JSON mode, thinking
        # off) — a cold first JSON call can blow the 8s budget and fail open
        # on the user's first click.
        resp = await asyncio.wait_for(
            llm._get_client().chat.completions.create(
                model=config.DEEPSEEK_MODEL,
                messages=[{"role": "user", "content": 'Respond ONLY with a json object. Example: {"ok": true}'}],
                response_format={"type": "json_object"},
                max_tokens=30,
                extra_body=llm._THINKING_OFF,
            ),
            timeout=15,
        )
        print(f"[startup] DeepSeek key valid + JSON path warmed, model={config.DEEPSEEK_MODEL}, status=200", flush=True)
    except Exception as e:
        print(f"[startup] DEEPSEEK_API_KEY INVALID or model error: {e!r}", flush=True)
        print("[startup] Server running in fail-open mode. All interrogations will approve.", flush=True)


class InterrogateRequest(BaseModel):
    user_id: int = 1
    product: dict = {}
    session_id: Optional[str] = None
    message: Optional[str] = None


def _new_session(user_id, product):
    session_id = "s_" + uuid.uuid4().hex[:12]
    ctx = db.get_context(user_id)
    session = {
        "id": session_id,
        "user_id": user_id,
        "product": product or {},
        "purchase_id": db.start_purchase(user_id, product or {}),
        "profile": ctx.get("profile") or {},
        "recent": ctx.get("recent") or [],
        "history": [],  # chat messages only: {"role": "assistant"|"user", "content": str}
        "turn": 0,  # assistant turns produced so far
    }
    sessions[session_id] = session
    return session


# The hard-approve rule (PRD §10): the model classifies `category` in the same
# single call; the backend enforces deterministically because temperature 0.8
# makes prompt-only enforcement flaky. Nobody's demo survives blocking insulin.
HARD_APPROVE_CATEGORIES = {"medical", "health", "food", "groceries", "safety", "work-gear"}


def _normalize(raw, final_turn):
    """Sanitize whatever the LLM returned into contract-safe values.

    APPROVE_THRESHOLD is the rehearsal tuning knob (PRD-C §11): when a final
    verdict comes back with a numeric score, the threshold decides approval —
    tune the number, not the prompt text.
    """
    category = raw.get("category")
    if isinstance(category, str) and category.strip().lower() in HARD_APPROVE_CATEGORIES:
        reply = raw.get("reply") if raw.get("verdict") == "approved" else None
        if not isinstance(reply, str) or not reply.strip():
            reply = f"That's {category.strip().lower().replace('-', ' ')} — essentials get a pass. Go ahead."
        return {"verdict": "approved", "score": 100, "reply": reply.strip()}

    verdict = raw.get("verdict")
    score = raw.get("score")
    score = int(score) if isinstance(score, (int, float)) and not isinstance(score, bool) else None
    reply = raw.get("reply")
    if not isinstance(reply, str) or not reply.strip():
        reply = "Go on."

    if verdict not in ("pending", "approved", "denied"):
        if score is None:
            # Unusable response mid-flight → fail open (never trap the user).
            return {"verdict": "approved", "score": None, "reply": "Fine. Go ahead."}
        verdict = "approved" if score >= config.APPROVE_THRESHOLD else ("pending" if score >= 40 else "denied")

    if verdict != "pending" and score is not None:
        verdict = "approved" if score >= config.APPROVE_THRESHOLD else "denied"

    if not final_turn and verdict == "denied":
        # Denials only land on the final turn — before that, keep the
        # conversation going so the user always gets to argue their case.
        verdict, score = "pending", None

    if final_turn and verdict == "pending":
        # No pending past the final turn — round down to denied (PRD-C §9).
        verdict = "denied"
        score = score if score is not None else 39

    return {"verdict": verdict, "score": score, "reply": reply.strip()}


def _last_user_message(history):
    for msg in reversed(history):
        if msg["role"] == "user":
            return msg["content"]
    return ""


def _fail_open_payload(req):
    try:
        saved = db.stats(req.user_id).get("saved_cents", 0)
    except Exception:
        saved = 0
    return {
        "session_id": req.session_id or "s_failopen",
        "verdict": "approved",
        "reply": "Backend's down. Enjoy your thing.",
        "turn": 0,
        "turns_remaining": 0,
        "score": None,
        "savings_total_cents": saved,
    }


async def _interrogate(req: InterrogateRequest):
    if req.session_id and req.session_id in sessions:
        session = sessions[req.session_id]
    else:
        session = _new_session(req.user_id, req.product)

    if req.message:
        session["history"].append({"role": "user", "content": req.message})
        db.log_turn(session["purchase_id"], session["turn"], "user", req.message)

    this_turn = session["turn"] + 1  # the assistant turn being produced now
    system = prompts.system_prompt(
        session["product"],
        session["profile"],
        session["recent"],
        turn=this_turn,
        max_turns=config.MAX_TURNS,
        has_message=bool(req.message),
    )
    messages = [{"role": "system", "content": system}, *session["history"]]

    raw = await llm.complete(messages)  # one call returns everything; never raises
    result = _normalize(raw, final_turn=this_turn >= config.MAX_TURNS)

    session["turn"] = this_turn
    session["history"].append({"role": "assistant", "content": result["reply"]})
    db.log_turn(session["purchase_id"], this_turn, "assistant", result["reply"])

    if result["verdict"] in ("approved", "denied"):
        db.finalize(
            session["purchase_id"],
            result["verdict"],
            result["score"],
            _last_user_message(session["history"]),
        )
        sessions.pop(session["id"], None)

    savings = db.stats(req.user_id)
    return {
        "session_id": session["id"],
        "verdict": result["verdict"],
        "reply": result["reply"],
        "turn": session["turn"],
        "turns_remaining": max(config.MAX_TURNS - session["turn"], 0),
        "score": result["score"],
        "savings_total_cents": savings.get("saved_cents", 0),
    }


@app.post("/api/interrogate")
async def interrogate(req: InterrogateRequest):
    try:
        return await _interrogate(req)
    except Exception as e:
        print(f"[interrogate] unexpected error: {e!r}. Failing open.")
        return _fail_open_payload(req)


@app.get("/api/stats/{user_id}")
def get_stats(user_id: int):
    try:
        return stats_module.get_stats(user_id)
    except Exception as e:
        print(f"[stats] error: {e!r}")
        return {"denied_count": 0, "approved_count": 0, "saved_cents": 0, "top_category": None}


@app.get("/api/profile/{user_id}")
def get_profile(user_id: int):
    try:
        # stats_module maps the sqlite `id` column to the contract's `user_id`.
        return stats_module.get_profile(user_id)
    except Exception as e:
        print(f"[profile] error: {e!r}")
        return {"user_id": user_id}


@app.put("/api/profile/{user_id}")
def put_profile(user_id: int, fields: dict):
    try:
        # D's db.put_profile UPDATEs all six columns, so merge partial input
        # over the current row before writing (onboarding form sends all six,
        # but partial PUTs must not KeyError).
        current = db.get_profile(user_id) or {}
        merged = {f: fields[f] if f in fields else current.get(f) for f in PROFILE_FIELDS}
        db.put_profile(user_id, merged)
        return stats_module.get_profile(user_id)
    except Exception as e:
        print(f"[profile] error: {e!r}")
        return {"user_id": user_id}
