import pandas as pd
def extract_csv(path: str) -> pd.DataFrame:
    return pd.read_csv(path)
