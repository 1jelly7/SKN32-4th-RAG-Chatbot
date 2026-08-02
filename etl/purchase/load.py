"""구매 도메인 쓰기 계정으로 검증된 frame만 적재할 미구현 adapter."""

# etl/purchase/load.py

import pandas as pd
from .types import LoadResult
import mysql.connector
from typing import Optional


# 전역 클라이언트 변수
_client: Optional["ETLMySQLClient"] = None


def initialize_client(host: str, user: str, password: str, database: str) -> "ETLMySQLClient":
    """전역 ETL MySQL 클라이언트를 초기화하고 반환한다."""
    global _client
    _client = ETLMySQLClient(host, user, password, database)
    return _client


class ETLMySQLClient:
    """ETL 전용 쓰기 계정으로만 적재하는 MySQL 어댑터."""

    # 적재가 허용된 테이블 목록
    ALLOWED_TABLES = {
        "purchase_orders",
        "po_lines",
        "vendors",
        "invoices",
        "goods_receipts"
    }

    def __init__(self, host: str, user: str, password: str, database: str) -> None:
        """쓰기 전용 연결 설정을 보관하고 비밀번호가 로그에 남지 않게 한다."""
        # TODO(implementation): 구매 쓰기 연결 설정만 보관하고 import/생성 시 접속하지
        # 않는다. read-only chatbot 계정과 자격증명 로그 사용을 금지한다.
        ...
        self.host = host
        self.user = user
        self.database = database
        self._password = password
        self._connection = None

    def _get_connection(self):
        """필요할 때만 연결을 생성한다."""
        if self._connection is None:
            self._connection = mysql.connector.connect(
                host=self.host,
                user=self.user,
                password=self._password,
                database=self.database
            )
        return self._connection

    def upsert(self, frame: pd.DataFrame, table: str) -> LoadResult:
        """검증 완료된 frame만 단일 트랜잭션으로 INSERT/UPSERT한다.

        table은 allowlist로 검증하고 값은 항상 파라미터 바인딩한다. 실패 시 전체 rollback,
        성공 시 commit하며 inserted/updated 수를 정확히 분리해 반환한다.
        """
        # TODO(implementation): 구매 allowlist와 자연키를 기준으로 parameterized UPSERT를
        # 단일 transaction에서 실행한다. 재실행 멱등성, rollback, inserted/updated 수,
        # 미허용 table 거부 테스트가 완료 조건이다.
        ...
        if table not in self.ALLOWED_TABLES:
            raise ValueError(f"테이블 '{table}'은 허용되지 않습니다. 허용된 테이블: {self.ALLOWED_TABLES}")

        connection = self._get_connection()
        cursor = connection.cursor()

        try:
            # 외래키 제약 임시 비활성화
            cursor.execute("SET FOREIGN_KEY_CHECKS=0")
            cursor.execute("START TRANSACTION")

            inserted = 0
            updated = 0

            # 각 행을 데이터베이스에 삽입
            for _, row in frame.iterrows():
                # 테이블에 있는 컬럼만 필터링
                cursor.execute(f"DESCRIBE {table}")
                existing_columns = {col[0] for col in cursor.fetchall()}

                # 존재하는 컬럼만 선택
                columns = [col for col in row.index if col in existing_columns]
                values = [row[col] for col in columns]

                if not columns:
                    print(f"  ⚠ 행을 건너뜀: 일치하는 컬럼이 없음")
                    continue

                # NULL 처리
                values = [None if pd.isna(v) else v for v in values]

                # INSERT 쿼리 작성 (간단한 구현)
                placeholders = ",".join(["%s"] * len(columns))
                column_names = ",".join(columns)
                query = f"INSERT INTO {table} ({column_names}) VALUES ({placeholders})"

                try:
                    cursor.execute(query, values)
                    inserted += 1
                except mysql.connector.Error as e:
                    if e.errno == 1062:  # Duplicate key error
                        updated += 1
                    else:
                        raise

            connection.commit()

            # 외래키 제약 다시 활성화
            cursor.execute("SET FOREIGN_KEY_CHECKS=1")
            cursor.close()

            return LoadResult(
                table=table,
                inserted_count=inserted,
                updated_count=updated
            )

        except Exception as e:
            connection.rollback()
            cursor.close()
            raise RuntimeError(f"Failed to upsert into {table}: {str(e)}")


def create_tables() -> None:
    """필요한 모든 테이블을 자동으로 생성한다."""
    if _client is None:
        raise RuntimeError("ETL 클라이언트가 초기화되지 않았습니다. initialize_client()를 먼저 호출하세요.")

    connection = _client._get_connection()
    cursor = connection.cursor()

    # 테이블 생성 SQL
    create_statements = [
        # 1. 공급업체 테이블
        """
        CREATE TABLE IF NOT EXISTS vendors (
            Vendor_ID INT PRIMARY KEY,
            Vendor_Code VARCHAR(50) UNIQUE NOT NULL,
            Vendor_Name VARCHAR(255) NOT NULL,
            Vendor_Type VARCHAR(50),
            Contact_Person VARCHAR(100),
            Email VARCHAR(100),
            Phone VARCHAR(20),
            Address VARCHAR(255),
            City VARCHAR(100),
            State VARCHAR(50),
            Country VARCHAR(100),
            Postal_Code VARCHAR(20),
            Payment_Terms VARCHAR(50),
            Currency VARCHAR(10),
            Rating INT,
            Active BOOLEAN DEFAULT TRUE,
            Created_Date DATETIME DEFAULT CURRENT_TIMESTAMP,
            Updated_Date DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
        """,

        # 2. 구매 주문 테이블
        """
        CREATE TABLE IF NOT EXISTS purchase_orders (
            PO_ID INT PRIMARY KEY,
            PO_Number VARCHAR(50) UNIQUE NOT NULL,
            PO_Date DATE NOT NULL,
            Vendor_ID INT NOT NULL,
            Requisition_ID INT,
            Status VARCHAR(50),
            Subtotal DECIMAL(10, 2),
            Tax_Amount DECIMAL(10, 2),
            Total_Amount DECIMAL(10, 2) NOT NULL,
            Currency VARCHAR(10),
            Expected_Delivery_Date DATE,
            Actual_Delivery_Date DATE,
            Notes TEXT,
            Created_Date DATETIME DEFAULT CURRENT_TIMESTAMP,
            Updated_Date DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (Vendor_ID) REFERENCES vendors(Vendor_ID) ON DELETE RESTRICT
        )
        """,

        # 3. 구매 주문 명세 테이블
        """
        CREATE TABLE IF NOT EXISTS po_lines (
            PO_Line_ID INT PRIMARY KEY,
            PO_ID INT NOT NULL,
            Item_ID INT NOT NULL,
            Item_Code VARCHAR(50),
            Item_Description VARCHAR(255),
            Description VARCHAR(255),
            Quantity INT NOT NULL,
            Unit_Price DECIMAL(10, 2),
            Discount_Percent DECIMAL(5, 2),
            Line_Total DECIMAL(10, 2),
            Received_Quantity INT DEFAULT 0,
            Accepted_Quantity INT DEFAULT 0,
            Rejected_Quantity INT DEFAULT 0,
            Unit_of_Measure VARCHAR(20),
            Created_Date DATETIME DEFAULT CURRENT_TIMESTAMP,
            Updated_Date DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (PO_ID) REFERENCES purchase_orders(PO_ID) ON DELETE CASCADE
        )
        """,

        # 4. 상품 수령 테이블
        """
        CREATE TABLE IF NOT EXISTS goods_receipts (
            GR_ID INT PRIMARY KEY,
            GR_Number VARCHAR(50) UNIQUE NOT NULL,
            PO_ID INT NOT NULL,
            Vendor_ID INT NOT NULL,
            GR_Date DATE,
            Receipt_Date DATE,
            Total_Quantity INT,
            Received_By VARCHAR(100),
            Warehouse_Location VARCHAR(100),
            Notes TEXT,
            Status VARCHAR(50),
            Created_Date DATETIME DEFAULT CURRENT_TIMESTAMP,
            Updated_Date DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (PO_ID) REFERENCES purchase_orders(PO_ID) ON DELETE CASCADE,
            FOREIGN KEY (Vendor_ID) REFERENCES vendors(Vendor_ID) ON DELETE RESTRICT
        )
        """,

        # 5. 송장 테이블
        """
        CREATE TABLE IF NOT EXISTS invoices (
            Invoice_ID INT PRIMARY KEY,
            Invoice_Number VARCHAR(50) UNIQUE NOT NULL,
            PO_ID INT NOT NULL,
            Vendor_ID INT NOT NULL,
            Invoice_Date DATE NOT NULL,
            Due_Date DATE,
            Subtotal DECIMAL(10, 2),
            Tax_Amount DECIMAL(10, 2),
            Total_Amount DECIMAL(10, 2) NOT NULL,
            Amount_Paid DECIMAL(10, 2),
            Outstanding_Amount DECIMAL(10, 2),
            Currency VARCHAR(10),
            Payment_Status VARCHAR(50),
            Payment_Date DATE,
            Payment_Method VARCHAR(50),
            Notes TEXT,
            Created_Date DATETIME DEFAULT CURRENT_TIMESTAMP,
            Updated_Date DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (PO_ID) REFERENCES purchase_orders(PO_ID) ON DELETE CASCADE,
            FOREIGN KEY (Vendor_ID) REFERENCES vendors(Vendor_ID) ON DELETE RESTRICT
        )
        """,
    ]

    try:
        for sql in create_statements:
            cursor.execute(sql)
            print(f"✓ 테이블 생성: {sql.split('CREATE TABLE IF NOT EXISTS')[1].split('(')[0].strip()}")

        connection.commit()
        print()
    except Exception as e:
        connection.rollback()
        raise RuntimeError(f"테이블 생성 실패: {str(e)}")
    finally:
        cursor.close()


def upsert(frame: pd.DataFrame, table: str) -> LoadResult:
    """기본 ETLMySQLClient로 위임하는 적재 편의 함수다; 검증 단계를 우회하면 안 된다."""
    # TODO(implementation): 검증 완료 precondition을 보존해 구매 client에만 위임한다.
    ...

    """기본 ETLMySQLClient로 위임하는 적재 편의 함수다."""
    if _client is None:
        raise RuntimeError("ETL 클라이언트가 초기화되지 않았습니다. initialize_client()를 먼저 호출하세요.")
    return _client.upsert(frame, table)