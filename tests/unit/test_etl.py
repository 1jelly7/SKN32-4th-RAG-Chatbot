import pandas as pd
<<<<<<< HEAD
from etl.finance.transform import transform
=======
from etl.purchase.transform import transform
>>>>>>> 2c10b076b3ac2d6eac31fb4a1f44ce787c5fd9e0
def test_transform_deduplicates(): assert len(transform(pd.DataFrame({'id':[1,1]}))) == 1
