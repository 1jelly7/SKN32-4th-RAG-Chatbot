import hashlib, json
def make_cache_key(state: dict) -> str:
    payload = {"q":" ".join(state.get("question", "").lower().split()), "user":state.get("user_context", {}).get("user_id", "anonymous")}
    return "answer:" + hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
