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

        table은 allowlist로 검증하고 값은 항상 파라미터 바인딩한다.
        실패 시 전체 rollback, 성공 시 commit하며 inserted/updated 수를 정확히 분리해 반환한다.
        """
        if table not in self.ALLOWED_TABLES:
            raise ValueError(
                f"테이블 '{table}'은 허용되지 않습니다. 허용된 테이블: {self.ALLOWED_TABLES}"
            )

        connection = self._get_connection()
        cursor = connection.cursor()

        try:
            # 외래키 제약 임시 비활성화
            cursor.execute("SET FOREIGN_KEY_CHECKS=0")
            cursor.execute("START TRANSACTION")

            # 테이블의 모든 컬럼 확인
            cursor.execute(f"DESCRIBE {table}")
            table_columns = {col[0] for col in cursor.fetchall()}

            inserted = 0
            updated = 0

            # 각 행을 데이터베이스에 삽입/업데이트
            for idx, row in frame.iterrows():
                # 프레임과 테이블에 모두 있는 컬럼만 선택
                columns = [col for col in row.index if col in table_columns]

                if not columns:
                    print(f"⚠️  {table} 행 {idx}: 일치하는 컬럼이 없음 (건너뜀)")
                    continue

                # 행 데이터 추출
                values = [row[col] for col in columns]

                # NULL 처리
                values = [None if pd.isna(v) else v for v in values]

                # INSERT 쿼리 작성
                column_names = ", ".join(columns)
                placeholders = ", ".join(["%s"] * len(columns))

                # UPDATE 부분 (중복 키에 대해)
                update_assignments = ", ".join([f"{col}=VALUES({col})" for col in columns])

                query = f"""
                    INSERT INTO {table} ({column_names})
                    VALUES ({placeholders})
                    ON DUPLICATE KEY UPDATE {update_assignments}
                """

                try:
                    cursor.execute(query, values)

                    # affected_rows:
                    # - 양수면 INSERT
                    # - 2이면 UPDATE (MySQL은 UPDATE를 2로 카운트)
                    affected = cursor.rowcount
                    if affected == 1:
                        inserted += 1
                    elif affected == 2:
                        updated += 1

                except mysql.connector.Error as e:
                    print(f"❌ {table} 행 {idx} 적재 실패: {str(e)}")
                    print(f"   컬럼: {columns}")
                    print(f"   값: {values}")
                    raise

            # 트랜잭션 커밋
            connection.commit()

            # 외래키 제약 다시 활성화
            cursor.execute("SET FOREIGN_KEY_CHECKS=1")

            print(f"✅ {table}: {inserted}건 삽입, {updated}건 업데이트")

            return LoadResult(
                table=table,
                inserted_count=inserted,
                updated_count=updated
            )

        except Exception as e:
            connection.rollback()
            raise RuntimeError(f"Failed to upsert into {table}: {str(e)}")
        finally:
            cursor.close()


def create_tables() -> None:
    """필요한 모든 테이블을 자동으로 생성한다.

    company_id를 포함하고, AUTO_INCREMENT 문제를 해결한 버전.
    """
    if _client is None:
        raise RuntimeError("ETL 클라이언트가 초기화되지 않았습니다. initialize_client()를 먼저 호출하세요.")

    connection = _client._get_connection()
    cursor = connection.cursor()

    # 테이블 생성 SQL (fresh_purchase_db_setup.sql과 일치)
    create_statements = [
        # 1. vendors 테이블 (먼저 생성 - 외래키 의존성이 없음)
        """
        CREATE TABLE IF NOT EXISTS vendors (
            Vendor_ID INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            company_id INT NOT NULL DEFAULT 1,
            Vendor_Code VARCHAR(50) NOT NULL,
            Vendor_Name VARCHAR(255) NOT NULL,
            Vendor_Type VARCHAR(50),
            Contact_Person VARCHAR(100),
            Email VARCHAR(100),
            Phone VARCHAR(20),
            Address VARCHAR(255),
            City VARCHAR(100),
            State VARCHAR(100),
            Country VARCHAR(100),
            Postal_Code VARCHAR(20),
            Payment_Terms VARCHAR(50),
            Currency VARCHAR(10),
            Rating DECIMAL(3,2),
            Active TINYINT DEFAULT 1,
            Created_Date DATETIME DEFAULT CURRENT_TIMESTAMP,
            Updated_Date DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            
            UNIQUE KEY uk_company_vendor (company_id, Vendor_Code),
            KEY idx_company_id (company_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,

        # 2. purchase_orders 테이블
        """
        CREATE TABLE IF NOT EXISTS purchase_orders (
            PO_ID INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            company_id INT NOT NULL DEFAULT 1,
            PO_Number VARCHAR(50) NOT NULL,
            PO_Date DATE NOT NULL,
            Vendor_ID INT NOT NULL,
            Requisition_ID INT,
            Subtotal DECIMAL(10,2),
            Tax_Amount DECIMAL(10,2),
            Total_Amount DECIMAL(10,2) NOT NULL,
            Currency VARCHAR(10),
            Status VARCHAR(50),
            Expected_Del_Date DATE,
            Actual_Deliv_Date DATE,
            Notes TEXT,
            Created_Date DATETIME DEFAULT CURRENT_TIMESTAMP,
            Updated_Date DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            
            UNIQUE KEY uk_company_po_number (company_id, PO_Number),
            KEY idx_vendor (Vendor_ID),
            KEY idx_company_id (company_id),
            CONSTRAINT purchase_orders_ibfk_1 FOREIGN KEY (Vendor_ID) 
                REFERENCES vendors(Vendor_ID) ON DELETE RESTRICT
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,

        # 3. po_lines 테이블
        """
        CREATE TABLE IF NOT EXISTS po_lines (
            PO_Line_ID INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            company_id INT NOT NULL DEFAULT 1,
            PO_ID INT NOT NULL,
            Item_ID INT,
            Item_Code VARCHAR(50),
            Item_Description VARCHAR(255),
            Description VARCHAR(255),
            Quantity INT NOT NULL,
            Unit_Price DECIMAL(10,2),
            Discount_Percent DECIMAL(5,2),
            Line_Total DECIMAL(10,2),
            Received_Quantity INT DEFAULT 0,
            Accepted_Quantity INT DEFAULT 0,
            Rejected_Quantity INT DEFAULT 0,
            Unit_of_Measure VARCHAR(20),
            Created_Date DATETIME DEFAULT CURRENT_TIMESTAMP,
            Updated_Date DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            
            KEY idx_po (PO_ID),
            KEY idx_company_id (company_id),
            CONSTRAINT po_lines_ibfk_1 FOREIGN KEY (PO_ID) 
                REFERENCES purchase_orders(PO_ID) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,

        # 4. invoices 테이블
        """
        CREATE TABLE IF NOT EXISTS invoices (
            Invoice_ID INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            company_id INT NOT NULL DEFAULT 1,
            Invoice_Number VARCHAR(50) NOT NULL,
            Invoice_Date DATE NOT NULL,
            PO_ID INT,
            Vendor_ID INT NOT NULL,
            Due_Date DATE,
            Subtotal DECIMAL(10,2),
            Tax_Amount DECIMAL(10,2),
            Total_Amount DECIMAL(10,2) NOT NULL,
            Amount_Paid DECIMAL(10,2),
            Outstanding_Amount DECIMAL(10,2),
            Currency VARCHAR(10),
            Payment_Status VARCHAR(50),
            Payment_Date DATE,
            Payment_Method VARCHAR(50),
            Notes TEXT,
            Created_Date DATETIME DEFAULT CURRENT_TIMESTAMP,
            Updated_Date DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            
            UNIQUE KEY uk_company_invoice_number (company_id, Invoice_Number),
            KEY idx_po (PO_ID),
            KEY idx_vendor (Vendor_ID),
            KEY idx_company_id (company_id),
            CONSTRAINT invoices_ibfk_1 FOREIGN KEY (PO_ID) 
                REFERENCES purchase_orders(PO_ID) ON DELETE SET NULL,
            CONSTRAINT invoices_ibfk_2 FOREIGN KEY (Vendor_ID) 
                REFERENCES vendors(Vendor_ID) ON DELETE RESTRICT
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,

        # 5. goods_receipts 테이블
        """
        CREATE TABLE IF NOT EXISTS goods_receipts (
            GR_ID INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            company_id INT NOT NULL DEFAULT 1,
            GR_Number VARCHAR(50) NOT NULL,
            PO_ID INT NOT NULL,
            Vendor_ID INT NOT NULL,
            Receipt_Date DATE,
            GR_Date DATE,
            PQ_Quantity INT,
            Received_By VARCHAR(100),
            Warehouse_Location VARCHAR(255),
            Notes TEXT,
            Status VARCHAR(50),
            Created_Date DATETIME DEFAULT CURRENT_TIMESTAMP,
            Updated_Date DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            
            UNIQUE KEY uk_company_gr_number (company_id, GR_Number),
            KEY idx_po (PO_ID),
            KEY idx_vendor (Vendor_ID),
            KEY idx_company_id (company_id),
            CONSTRAINT goods_receipts_ibfk_1 FOREIGN KEY (PO_ID) 
                REFERENCES purchase_orders(PO_ID) ON DELETE RESTRICT,
            CONSTRAINT goods_receipts_ibfk_2 FOREIGN KEY (Vendor_ID) 
                REFERENCES vendors(Vendor_ID) ON DELETE RESTRICT
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    ]

    try:
        for sql in create_statements:
            cursor.execute(sql)
            # 테이블 이름 추출
            table_name = sql.split("CREATE TABLE IF NOT EXISTS")[1].split("(")[0].strip()
            print(f"✅ 테이블 생성/확인: {table_name}")

        connection.commit()
        print("\n✅ 모든 테이블이 준비되었습니다.\n")

    except Exception as e:
        connection.rollback()
        raise RuntimeError(f"테이블 생성 실패: {str(e)}")
    finally:
        cursor.close()


def upsert(frame: pd.DataFrame, table: str) -> LoadResult:
    """기본 ETLMySQLClient로 위임하는 적재 편의 함수다.

    검증 완료된 frame만 호출해야 한다.
    """
    if _client is None:
        raise RuntimeError(
            "ETL 클라이언트가 초기화되지 않았습니다. initialize_client()를 먼저 호출하세요."
        )
    return _client.upsert(frame, table)