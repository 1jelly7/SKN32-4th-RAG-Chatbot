import pandas as pd
def validate(frame: pd.DataFrame, required: list[str]) -> None:
    missing=set(required)-set(frame.columns)
    if missing: raise ValueError(f"Missing columns: {missing}")
    if frame[required].isnull().any().any(): raise ValueError("Required values cannot be null")
