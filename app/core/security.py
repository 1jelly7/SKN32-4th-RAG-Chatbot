def build_user_context(user_id: str = "anonymous", role: str = "user") -> dict:
    return {"user_id": user_id, "role": role}
