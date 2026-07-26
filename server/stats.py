import db

def get_stats(user_id: int) -> dict:
    return db.stats(user_id)

def get_profile(user_id: int) -> dict:
    profile = db.get_profile(user_id)
    if not profile:
        return {}
    profile["user_id"] = profile.pop("id", user_id)
    return profile

def update_profile(user_id: int, profile: dict) -> None:
    db.put_profile(user_id, profile)
