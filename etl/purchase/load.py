"""구매 전용 쓰기 계정과 UPSERT 책임을 둔다."""

from __future__ import annotations

import pandas as pd
import pymysql

from etl.purchase.config import MySQLWriteConfig
from etl.purchase.ddl import build_create_table_sql
from etl.purchase.schema import PURCHASE_SCHEMA
from etl.purchase.types import LoadResult


def _to_db_value(value):
    """pandas의 pd.NA/np.nan/NaT를 MySQL이 이해하는 None으로 바꾼다.

    DataFrame.where(pd.notnull(df), None)은 nullable Int64 등 확장 타입 컬럼에서
    pd.NA를 제대로 치환하지 못하고 그대로 남기는 경우가 있어(그 결과 pymysql이
    문자열 '<NA>'를 그대로 보내 정수 컬럼에서 오류가 난다), 값 단위로 pd.isna()를
    적용한다(etl/sales/load.py와 동일한 이유).
    """
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


class PurchaseETLMySQLClient:
    """구매 도메인에 허용된 테이블만 UPSERT하는 쓰기 어댑터.

    - PURCHASE_DB_*(구매 전용 ETL 계정)만 사용한다. 조회용 read-only 계정
      (purchase_reader)과는 완전히 분리되어 있다
      (mcp_servers/data_tools/purchase/mysql.py 소유).
    - PURCHASE_SCHEMA(etl/purchase/schema.py)에 정의되지 않은 테이블은 거부한다.
    - PK 충돌 시 INSERT ... ON DUPLICATE KEY UPDATE로 처리해 동일 원천을
      재실행해도 행 수가 늘어나지 않는다 (ETL 멱등성). PK에 AUTO_INCREMENT를
      붙이지 않는다 — 원천이 이미 안정적인 id를 갖고 있어, 붙이면 재실행마다
      새 행이 생겨 멱등성이 깨진다.
    - `purchase` 데이터베이스 자체는 이 클라이언트가 만들지 않는다. 프로젝트를
      처음 설정하는 사람이 `database/purchase/create_purchase_db.sql`을 1회
      실행해 만들어둔다는 것을 전제로 한다.
    """

    def __init__(self, config: MySQLWriteConfig | None = None) -> None:
        self._config = config or MySQLWriteConfig.from_env()

    def _connect(self):
        return pymysql.connect(
            host=self._config.host,
            user=self._config.user,
            password=self._config.password,
            database=self._config.database,
            port=self._config.port,
            charset="utf8mb4",
            autocommit=False,
        )

    def ensure_table(self, table: str) -> None:
        """대상 테이블이 없으면 database/purchase/ddl.sql 기준으로 생성한다."""
        if table not in PURCHASE_SCHEMA:
            raise ValueError(f"'{table}'은(는) 구매 도메인 허용 테이블이 아닙니다.")
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(build_create_table_sql(table))
            conn.commit()
        finally:
            conn.close()

    def upsert(self, frame: pd.DataFrame, table: str) -> LoadResult:
        """frame을 table에 UPSERT하고 삽입/갱신 건수를 반환한다."""
        if table not in PURCHASE_SCHEMA:
            raise ValueError(f"'{table}'은(는) 구매 도메인 허용 테이블이 아닙니다.")

        columns = [c["name"] for c in PURCHASE_SCHEMA[table]["columns"]]
        pk = PURCHASE_SCHEMA[table]["pk"]

        missing = [c for c in columns if c not in frame.columns]
        if missing:
            raise ValueError(f"'{table}' 적재 대상에 컬럼이 없습니다: {missing}")

        ordered = frame[columns]

        col_list = ", ".join(f"`{c}`" for c in columns)
        placeholders = ", ".join(["%s"] * len(columns))
        update_clause = ", ".join(f"`{c}`=VALUES(`{c}`)" for c in columns if c != pk)
        sql = (
            f"INSERT INTO `{table}` ({col_list}) VALUES ({placeholders}) "
            f"ON DUPLICATE KEY UPDATE {update_clause}"
        )

        inserted = 0
        updated = 0
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(build_create_table_sql(table))
                for row in ordered.itertuples(index=False, name=None):
                    row = tuple(_to_db_value(v) for v in row)
                    cur.execute(sql, row)
                    # MySQL 규칙: 신규 INSERT는 rowcount=1, 값이 바뀐 UPDATE는 rowcount=2,
                    # 값이 동일해 변경이 없는 UPDATE는 rowcount=0.
                    if cur.rowcount == 1:
                        inserted += 1
                    elif cur.rowcount == 2:
                        updated += 1
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        return {"table": table, "inserted_count": inserted, "updated_count": updated}
