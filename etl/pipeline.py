from etl.extract import extract_csv
from etl.transform import transform
from etl.validate import validate
from etl.load import upsert
def run_csv_pipeline(path: str, table: str, required: list[str]) -> int:
    frame = transform(extract_csv(path)); validate(frame, required); return upsert(frame, table)
