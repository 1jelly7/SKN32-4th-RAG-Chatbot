"""판매 extract → transform → validate → load 파이프라인 진입점."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from etl.sales.extract import extract_csv, extract_excel_sheet
from etl.sales.load import SalesETLMySQLClient
from etl.sales.schema import SALES_SCHEMA
from etl.sales.transform import transform
from etl.sales.types import PipelineResult
from etl.sales.validate import validate

MODULE = "etl.sales.pipeline"
LOG_PATH = Path("logs/etl_sales.log.txt")


def _log(level: str, event: str, message: str = "") -> None:
    ts = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    line = f"{ts} | {level} | {MODULE} | {event} | {message}\n"
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line)
    print(line, end="")


def _bool_to_int(value: Any):
    if pd.isna(value):
        return pd.NA
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip().upper()
    if text in ("TRUE", "1", "Y", "YES"):
        return 1
    if text in ("FALSE", "0", "N", "NO"):
        return 0
    return pd.NA


def _coerce_boolean_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """스키마상 TINYINT(1)인 컬럼의 'TRUE'/'FALSE' 텍스트를 1/0으로 정리한다.

    transform.py의 astype()만으로는 문자열 'TRUE'/'FALSE'를 올바르게 불리언으로
    변환할 수 없어 transform 호출 전에 미리 정리한다.
    """
    result = frame.copy()
    for col in columns:
        if col in result.columns:
            result[col] = result[col].map(_bool_to_int)
    return result


def _type_mapping_for(table: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for col in SALES_SCHEMA[table]["columns"]:
        if col["type"] == "BIGINT" or col["type"] == "TINYINT(1)":
            mapping[col["name"]] = "Int64"  # pandas nullable integer
        elif col["type"].startswith("DECIMAL"):
            mapping[col["name"]] = "float64"
    return mapping


def _boolean_columns(table: str) -> list[str]:
    return [c["name"] for c in SALES_SCHEMA[table]["columns"] if c["type"] == "TINYINT(1)"]


def _run(frame: pd.DataFrame, source_label: str, table: str, required_columns: list[str]) -> PipelineResult:
    _log("INFO", "extract_done", f"source={source_label} table={table} rows={len(frame)}")

    prepared = frame
    if table in SALES_SCHEMA:
        prepared = _coerce_boolean_columns(frame, _boolean_columns(table))
        type_mapping = _type_mapping_for(table)
    else:
        type_mapping = None

    transformed = transform(prepared, type_mapping=type_mapping)
    dropped = len(prepared) - len(transformed)
    if dropped:
        _log("INFO", "duplicates_dropped", f"table={table} dropped_rows={dropped}")

    report = validate(transformed, required_columns)
    _log(
        "INFO" if report["is_valid"] else "ERROR",
        "validate_done",
        f"table={table} is_valid={report['is_valid']} "
        f"invalid_rows={report['invalid_row_count']} errors={report['errors']}",
    )

    if not report["is_valid"]:
        _log("ERROR", "pipeline_aborted", f"table={table} reason=missing_required_columns")
        return {"source_path": source_label, "validation": report, "load": None}

    client = SalesETLMySQLClient()
    load_result = client.upsert(transformed, table)
    _log(
        "INFO",
        "table_loaded",
        f"table={table} inserted={load_result['inserted_count']} "
        f"updated={load_result['updated_count']}",
    )

    return {"source_path": source_label, "validation": report, "load": load_result}


def run_csv_pipeline(path: Path, table: str, required_columns: list[str]) -> PipelineResult:
    """판매 ETL 단계를 순서대로 실행한다."""
    _log("INFO", "pipeline_start", f"source={path} table={table}")
    try:
        frame = extract_csv(path)
        result = _run(frame, str(path), table, required_columns)
        _log("INFO", "pipeline_success", f"table={table}")
        return result
    except Exception as exc:  # noqa: BLE001 - 배치 실패를 그대로 로그에 남긴다
        _log("ERROR", "pipeline_failed", f"table={table} {type(exc).__name__}: {exc}")
        raise


def run_excel_pipeline(
    path: Path, sheet_name: str, table: str, required_columns: list[str]
) -> PipelineResult:
    """엑셀 시트를 원천으로 판매 ETL 단계를 순서대로 실행한다.

    시트별 CSV가 아직 준비되지 않은 소스(ERP_Sales_Data_Full.xlsx)를 위한 진입점이며,
    계약(반환 타입·단계 순서)은 run_csv_pipeline과 동일하다.
    """
    _log("INFO", "pipeline_start", f"source={path} sheet={sheet_name} table={table}")
    try:
        frame = extract_excel_sheet(path, sheet_name)
        result = _run(frame, f"{path}#{sheet_name}", table, required_columns)
        _log("INFO", "pipeline_success", f"table={table}")
        return result
    except Exception as exc:  # noqa: BLE001
        _log("ERROR", "pipeline_failed", f"table={table} {type(exc).__name__}: {exc}")
        raise
