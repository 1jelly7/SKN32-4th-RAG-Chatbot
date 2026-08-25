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
    """판매 ETL 쓰기 연결에 필요한 최소 설정."""

    host: str
    user: str
    password: str
    database: str
    port: int = 3306

    @classmethod
    def from_env(cls) -> "MySQLWriteConfig":
        """환경 변수에서 필수 쓰기 설정을 검증해 구성한다.

        DOCUMENT_DB_*와 동일한 패턴으로, SALES_DB_*를 판매 도메인 전용
        독립 블록으로 사용한다. 다른 도메인(구매 등)과 MYSQL_DATABASE 같은
        공용 변수를 공유하지 않아, 다른 팀이 그 값을 바꿔도 판매 ETL이
        엉뚱한 DB에 접속하는 사고를 막는다.
        """
        host = os.getenv("SALES_DB_HOST", "localhost")
        user = os.getenv("SALES_DB_USER")
        password = os.getenv("SALES_DB_PASSWORD")
        database = os.getenv("SALES_DB_DATABASE")

        missing = [
            name
            for name, val in [
                ("SALES_DB_USER", user),
                ("SALES_DB_DATABASE", database),
            ]
            if not val
        ]
        if missing:
            raise RuntimeError(
                f".env에 다음 값이 비어 있습니다: {', '.join(missing)}. "
                "판매 DB 쓰기 계정 정보를 .env에 채워주세요."
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
    "data/raw/source_data/ERP_Sales_Data_Full_5y.xlsx",
)

LOG_PATH = os.getenv("SALES_ETL_LOG_PATH", "logs/etl_sales.log.txt")
