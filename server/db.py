"""SwiperNoSwiping — SQLite access layer.

Owned by D. Provides the persistence layer that C and B depend on.
All function signatures frozen at T+0:20 — do not rename.
"""

import sqlite3
import os

DB_PATH = os.environ.get("SWIPERNO_DB_PATH", "swiperno.db")


def _conn():
    """Open a connection with row_factory for dict-like access."""
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    return c


def init():
    """Run schema.sql to create tables and indexes."""
    import os as _os
    schema_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "schema.sql")
    with open(schema_path) as f:
        _conn().executescript(f.read())


def get_context(user_id: int) -> dict:
    """Return {'profile': {...}, 'recent': [...]} — last 5 purchases, newest first."""
    with _conn() as db:
        profile_row = db.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()

        if not profile_row:
            return {"profile": {}, "recent": []}

        profile = dict(profile_row)
        # Remove internal id from the exposed profile dict
        profile.pop("id", None)
        profile.pop("created_at", None)

        recent_rows = db.execute(
            """SELECT product_title, price_cents, currency, verdict, category, created_at
               FROM purchases
               WHERE user_id = ?
               ORDER BY created_at DESC
               LIMIT 5""",
            (user_id,),
        ).fetchall()

        recent = [dict(r) for r in recent_rows]
        return {"profile": profile, "recent": recent}


def start_purchase(user_id: int, product: dict) -> int:
    """Insert a purchase row with verdict='abandoned'. Returns the new purchase_id."""
    with _conn() as db:
        cur = db.execute(
            """INSERT INTO purchases
               (user_id, site, product_title, price_cents, currency, url, image_url, verdict)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'abandoned')""",
            (
                user_id,
                product.get("site"),
                product.get("title"),
                product.get("price_cents"),
                product.get("currency", "USD"),
                product.get("url"),
                product.get("image_url"),
            ),
        )
        db.commit()
        return cur.lastrowid


def log_turn(purchase_id: int, idx: int, role: str, content: str) -> None:
    """Record one conversation turn (assistant question or user response)."""
    with _conn() as db:
        db.execute(
            "INSERT INTO turns (purchase_id, idx, role, content) VALUES (?, ?, ?, ?)",
            (purchase_id, idx, role, content),
        )
        db.commit()


def finalize(purchase_id: int, verdict: str, score: int, justification: str) -> None:
    """Update the purchase row with the final verdict, score, and justification."""
    with _conn() as db:
        db.execute(
            """UPDATE purchases
               SET verdict = ?, score = ?, final_justification = ?
               WHERE id = ?""",
            (verdict, score, justification, purchase_id),
        )
        db.commit()


def stats(user_id: int) -> dict:
    """Return {'denied_count', 'approved_count', 'saved_cents', 'top_category'}."""
    with _conn() as db:
        denied = db.execute(
            "SELECT COUNT(*) FROM purchases WHERE user_id = ? AND verdict = 'denied'",
            (user_id,),
        ).fetchone()[0]

        approved = db.execute(
            "SELECT COUNT(*) FROM purchases WHERE user_id = ? AND verdict = 'approved'",
            (user_id,),
        ).fetchone()[0]

        saved = db.execute(
            "SELECT COALESCE(SUM(price_cents), 0) FROM purchases WHERE user_id = ? AND verdict = 'denied'",
            (user_id,),
        ).fetchone()[0]

        top = db.execute(
            """SELECT category
               FROM purchases
               WHERE user_id = ? AND verdict = 'denied'
               GROUP BY category
               ORDER BY COUNT(*) DESC
               LIMIT 1""",
            (user_id,),
        ).fetchone()

        return {
            "denied_count": denied,
            "approved_count": approved,
            "saved_cents": saved,
            "top_category": top[0] if top else None,
        }


def get_profile(user_id: int) -> dict:
    """Return the user profile row as a dict, or empty dict if not found."""
    with _conn() as db:
        row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            return {}
        profile = dict(row)
        profile.pop("id", None)
        profile.pop("created_at", None)
        return profile


def put_profile(user_id: int, profile: dict) -> None:
    """Upsert a user profile row."""
    with _conn() as db:
        existing = db.execute(
            "SELECT id FROM users WHERE id = ?", (user_id,)
        ).fetchone()

        if existing:
            db.execute(
                """UPDATE users
                   SET display_name = ?, income_band = ?, monthly_budget_cents = ?,
                       savings_goal = ?, goal_target_cents = ?, known_weakness = ?
                   WHERE id = ?""",
                (
                    profile.get("display_name"),
                    profile.get("income_band"),
                    profile.get("monthly_budget_cents"),
                    profile.get("savings_goal"),
                    profile.get("goal_target_cents"),
                    profile.get("known_weakness"),
                    user_id,
                ),
            )
        else:
            db.execute(
                """INSERT INTO users
                   (id, display_name, income_band, monthly_budget_cents,
                    savings_goal, goal_target_cents, known_weakness)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    user_id,
                    profile.get("display_name"),
                    profile.get("income_band"),
                    profile.get("monthly_budget_cents"),
                    profile.get("savings_goal"),
                    profile.get("goal_target_cents"),
                    profile.get("known_weakness"),
                ),
            )
        db.commit()
