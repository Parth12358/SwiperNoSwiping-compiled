import sqlite3
import os

DB_PATH = "swiperno.db"

def init():
    """Run schema.sql to create tables."""
    pass

def get_context(user_id: int) -> dict:
    """Return {'profile': {...}, 'recent': [...]} — last 5 purchases, newest first."""
    pass

def start_purchase(user_id: int, product: dict) -> int:
    """Insert with verdict='abandoned'. Returns purchase_id."""
    pass

def log_turn(purchase_id: int, idx: int, role: str, content: str) -> None:
    pass

def finalize(purchase_id: int, verdict: str, score: int, justification: str) -> None:
    pass

def stats(user_id: int) -> dict:
    """Return {'denied_count','approved_count','saved_cents','top_category'}"""
    pass

def get_profile(user_id: int) -> dict:
    pass

def put_profile(user_id: int, profile: dict) -> None:
    pass
