from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import db
import llm
import config

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.post("/api/interrogate")
async def interrogate(req: dict):
    pass

@app.get("/api/stats/{user_id}")
async def stats(user_id: int):
    pass

@app.get("/api/profile/{user_id}")
async def get_profile(user_id: int):
    pass

@app.put("/api/profile/{user_id}")
async def put_profile(user_id: int, body: dict):
    pass
