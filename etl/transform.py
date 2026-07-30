import pandas as pd
def transform(frame: pd.DataFrame) -> pd.DataFrame:
    # TODO: normalize columns/types, handle nulls and duplicates.
    return frame.drop_duplicates().copy()
