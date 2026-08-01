"""
판매(Sales) ETL 설정 로더.

.env 값을 읽어 MySQL 쓰기(ETL) 연결 정보를 만든다.
- ETL은 쓰기 계정(MYSQL_WRITE_*)만 사용한다.
- 챗봇 조회 경로(mcp_servers/data_tools/sales/mysql.py)는 읽기 계정(MYSQL_READ_*)을
  별도로 사용하며, 이 모듈이 다루는 범위가 아니다.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# 프로젝트 루트의 .env를 로드한다. 이미 로드되어 있으면 조용히 무시된다.
load_dotenv()


@dataclass(frozen=True)
class MySQLWriteConfig:
    host: str
    user: str
    password: str
    database: str
    port: int = 3306

    @classmethod
    def from_env(cls) -> "MySQLWriteConfig":
        host = os.getenv("MYSQL_WRITE_HOST", "localhost")
        user = os.getenv("MYSQL_WRITE_USER")
        password = os.getenv("MYSQL_WRITE_PASSWORD")
        database = os.getenv("MYSQL_DATABASE")

        missing = [
            name
            for name, val in [
                ("MYSQL_WRITE_USER", user),
                ("MYSQL_DATABASE", database),
            ]
            if not val
        ]
        if missing:
            raise RuntimeError(
                f".env에 다음 값이 비어 있습니다: {', '.join(missing)}. "
                "etl_writer 계정 정보를 .env에 채워주세요."
            )

        return cls(
            host=host,
            user=user,
            password=password or "",
            database=database,
        )


# 소스 엑셀 워크북 기본 경로. 필요하면 pipeline 호출 시 override 한다.
DEFAULT_SOURCE_XLSX = os.getenv(
    "SALES_SOURCE_XLSX",
    "data/raw/source_data/ERP_Sales_Data_Full.xlsx",
)

LOG_PATH = os.getenv("SALES_ETL_LOG_PATH", "logs/etl_sales.log.txt")
