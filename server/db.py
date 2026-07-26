import sqlite3
import os

DB_PATH = os.environ.get("SWIPERNO_DB_PATH", "swiperno.db")

def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def init():
    with open(os.path.join(os.path.dirname(__file__), "schema.sql")) as f:
        sql = f.read()
    with _conn() as db:
        db.executescript(sql)

def get_context(user_id: int) -> dict:
    with _conn() as db:
        profile = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        profile = dict(profile) if profile else {}
        rows = db.execute(
            "SELECT product_title, price_cents, verdict, category, created_at FROM purchases WHERE user_id=? ORDER BY created_at DESC LIMIT 5",
            (user_id,)
        ).fetchall()
        recent = [dict(r) for r in rows]
        return {"profile": profile, "recent": recent}

def start_purchase(user_id: int, product: dict) -> int:
    with _conn() as db:
        cur = db.execute(
            "INSERT INTO purchases (user_id, site, product_title, price_cents, currency, url, image_url, category, verdict) VALUES (?,?,?,?,?,?,?,?,'abandoned')",
            (user_id, product.get("site"), product.get("title"), product.get("price_cents"),
             product.get("currency", "USD"), product.get("url"), product.get("image_url"), product.get("category"))
        )
        return cur.lastrowid

def log_turn(purchase_id: int, idx: int, role: str, content: str) -> None:
    with _conn() as db:
        db.execute(
            "INSERT INTO turns (purchase_id, idx, role, content) VALUES (?,?,?,?)",
            (purchase_id, idx, role, content)
        )

def finalize(purchase_id: int, verdict: str, score: int, justification: str) -> None:
    with _conn() as db:
        db.execute(
            "UPDATE purchases SET verdict=?, score=?, final_justification=? WHERE id=?",
            (verdict, score, justification, purchase_id)
        )

def stats(user_id: int) -> dict:
    with _conn() as db:
        denied = db.execute("SELECT COUNT(*) FROM purchases WHERE user_id=? AND verdict='denied'", (user_id,)).fetchone()[0]
        approved = db.execute("SELECT COUNT(*) FROM purchases WHERE user_id=? AND verdict='approved'", (user_id,)).fetchone()[0]
        saved = db.execute("SELECT COALESCE(SUM(price_cents),0) FROM purchases WHERE user_id=? AND verdict='denied'", (user_id,)).fetchone()[0]
        top = db.execute(
            "SELECT category FROM purchases WHERE user_id=? AND verdict='denied' GROUP BY category ORDER BY COUNT(*) DESC LIMIT 1",
            (user_id,)
        ).fetchone()
        return {
            "denied_count": denied,
            "approved_count": approved,
            "saved_cents": saved,
            "top_category": top[0] if top else None
        }

def get_profile(user_id: int) -> dict:
    with _conn() as db:
        row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return dict(row) if row else {}

def put_profile(user_id: int, profile: dict) -> None:
    with _conn() as db:
        db.execute(
            "UPDATE users SET display_name=?, income_band=?, monthly_budget_cents=?, savings_goal=?, goal_target_cents=?, known_weakness=? WHERE id=?",
            (profile["display_name"], profile["income_band"], profile["monthly_budget_cents"],
             profile["savings_goal"], profile["goal_target_cents"], profile["known_weakness"], user_id)
        )
