def build_metadata(document: dict) -> dict:
    return {"source": document.get("path", ""), "allowed_roles": ["user"]}
