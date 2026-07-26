from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import db
import llm
import config
import stats as stats_mod

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.post("/api/interrogate")
async def interrogate(req: dict):
    # Owned by C — stubbed until integration
    pass

@app.get("/api/stats/{user_id}")
async def stats(user_id: int):
    """Return denied_count, approved_count, saved_cents, top_category."""
    try:
        return stats_mod.get_stats(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/profile/{user_id}")
async def get_profile(user_id: int):
    """Return the user profile dict."""
    try:
        profile = stats_mod.get_profile(user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="User not found")
        return profile
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/profile/{user_id}")
async def put_profile(user_id: int, body: dict):
    """Upsert a user profile."""
    try:
        stats_mod.update_profile(user_id, body)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
