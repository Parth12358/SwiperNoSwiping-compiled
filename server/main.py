import os
import uuid
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import db
import llm
import prompts
import config
import stats as stats_module

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

sessions = {}

@app.on_event("startup")
async def startup():
    db.init()
    if os.environ.get("MOCK_LLM", "0") == "1":
        print("[swiperno:server] MOCK_LLM=1 — no DeepSeek calls will be made")

def _new_session(user_id: int, product: dict) -> dict:
    session_id = str(uuid.uuid4())[:12]
    purchase_id = db.start_purchase(user_id, product)
    session = {
        "id": session_id,
        "user_id": user_id,
        "product": product,
        "purchase_id": purchase_id,
        "turn": 0,
        "history": [],
    }
    sessions[session_id] = session
    return session

@app.post("/api/interrogate")
async def interrogate(req: dict):
    user_id = req.get("user_id", 1)
    product = req.get("product", {})
    session_id = req.get("session_id")
    message = req.get("message")

    if session_id and session_id in sessions:
        session = sessions[session_id]
    else:
        session = _new_session(user_id, product)

    if message:
        session["history"].append({"role": "user", "content": message})
        db.log_turn(session["purchase_id"], session["turn"] + 1, "user", message)

    ctx = db.get_context(user_id)
    session["turn"] += 1

    msgs = prompts.build_prompt(
        ctx.get("profile"), ctx.get("recent"),
        product, session["history"], session["turn"]
    )

    result = await llm.complete(msgs)

    session["history"].append({"role": "assistant", "content": result["reply"]})
    db.log_turn(session["purchase_id"], session["turn"], "assistant", result["reply"])

    if result["verdict"] in ("approved", "denied"):
        justification = session["history"][-2]["content"] if len(session["history"]) >= 2 else ""
        db.finalize(session["purchase_id"], result["verdict"], result.get("score") or 0, justification)
        sessions.pop(session["id"], None)

    savings = db.stats(user_id)

    return {
        "session_id": session["id"],
        "verdict": result["verdict"],
        "reply": result["reply"],
        "turn": session["turn"],
        "turns_remaining": config.MAX_TURNS - session["turn"],
        "score": result.get("score"),
        "savings_total_cents": savings["saved_cents"],
    }

@app.get("/api/stats/{user_id}")
async def stats(user_id: int):
    return stats_module.get_stats(user_id)

@app.get("/api/profile/{user_id}")
async def get_profile(user_id: int):
    return stats_module.get_profile(user_id)

@app.put("/api/profile/{user_id}")
async def put_profile(user_id: int, body: dict):
    stats_module.update_profile(user_id, body)
    return {"status": "ok"}
