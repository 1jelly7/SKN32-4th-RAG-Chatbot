import pandas as pd
from etl.finance.transform import transform
def test_transform_deduplicates(): assert len(transform(pd.DataFrame({'id':[1,1]}))) == 1
