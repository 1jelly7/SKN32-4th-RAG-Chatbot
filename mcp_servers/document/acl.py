def filter_allowed(documents: list[dict], user_context: dict) -> list[dict]:
    role = user_context.get("role", "user")
    return [d for d in documents if role in d.get("allowed_roles", [role])]
