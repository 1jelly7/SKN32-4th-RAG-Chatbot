def validate_sql(sql: str) -> None:
    normalized = sql.strip().lower()
    if not normalized.startswith("select") or ";" in normalized.rstrip(";"):
        raise ValueError("Only a single SELECT statement is allowed")
