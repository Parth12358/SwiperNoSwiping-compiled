"""SwiperNoSwiping — stats & profile route logic.

Owned by D. Imported by main.py for the /api/stats and /api/profile endpoints.
"""

import db


def get_stats(user_id: int) -> dict:
    """Return denied_count, approved_count, saved_cents, top_category."""
    return db.stats(user_id)


def get_profile(user_id: int) -> dict:
    """Return the user profile dict."""
    return db.get_profile(user_id)


def update_profile(user_id: int, profile: dict) -> None:
    """Upsert the user profile from a request body."""
    db.put_profile(user_id, profile)
