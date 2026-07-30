import pandas as pd
def upsert(frame: pd.DataFrame, table: str) -> int:
    # TODO: use ETL-only MySQL credentials, transaction and ON DUPLICATE KEY UPDATE.
    return len(frame)
