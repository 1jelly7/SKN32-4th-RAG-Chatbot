"""구매 extract → transform → validate → load 파이프라인 진입점."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from etl.purchase.extract import extract_csv, extract_excel_sheet
from etl.purchase.load import PurchaseETLMySQLClient
from etl.purchase.schema import PURCHASE_SCHEMA, boolean_columns, type_mapping_for
from etl.purchase.transform import transform
from etl.purchase.types import PipelineResult
from etl.purchase.validate import validate

MODULE = "etl.purchase.pipeline"
LOG_PATH = Path("logs/etl_purchase.log.txt")


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

    구매 원천의 Is_Active는 실제로 pandas bool dtype이라 이 강제 없이도
    astype("Int64")가 통과하지만, sales와 동일하게 방어적으로 유지한다.
    """
    result = frame.copy()
    for col in columns:
        if col in result.columns:
            result[col] = result[col].map(_bool_to_int)
    return result


def _run(
    frame: pd.DataFrame, source_label: str, table: str, required_columns: list[str]
) -> PipelineResult:
    _log(
        "INFO", "extract_done", f"source={source_label} table={table} rows={len(frame)}"
    )

    prepared = frame
    if table in PURCHASE_SCHEMA:
        prepared = _coerce_boolean_columns(frame, boolean_columns(table))
        type_mapping = type_mapping_for(table)
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
        _log("ERROR", "pipeline_aborted", f"table={table} reason=validation_failed")
        return {"source_path": source_label, "validation": report, "load": None}

    client = PurchaseETLMySQLClient()
    load_result = client.upsert(transformed, table)
    _log(
        "INFO",
        "table_loaded",
        f"table={table} inserted={load_result['inserted_count']} "
        f"updated={load_result['updated_count']}",
    )

    return {"source_path": source_label, "validation": report, "load": load_result}


def run_csv_pipeline(
    path: Path, table: str, required_columns: list[str]
) -> PipelineResult:
    """구매 ETL 단계를 순서대로 실행한다(CSV 원천용)."""
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
    """엑셀 시트를 원천으로 구매 ETL 단계를 순서대로 실행한다.

    계약(반환 타입·단계 순서)은 run_csv_pipeline과 동일하다(etl/sales와 동형).
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
