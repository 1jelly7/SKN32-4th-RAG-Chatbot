    #!/usr/bin/env python3
"""
ERP 구매 분석 데이터를 MySQL 데이터베이스에 적재하는 메인 ETL 스크립트

구성:
- 데이터 소스: data/raw/source_data/ERP_Purchasing_Analytics.xlsx
- 대상 데이터베이스: MySQL purchase 데이터베이스
- 사용자: purchase
"""

from pathlib import Path
from etl.purchase.pipeline import run_csv_pipeline
from etl.purchase.load import initialize_client, create_tables, _client

# 데이터베이스 연결 정보
DB_CONFIG = {
    'host': 'localhost',  # MySQL 호스트 (로컬 개발용)
    'user': 'purchase',  # 사용자명
    'password': '1234',  # 여기에 비밀번호를 입력하세요
    'database': 'purchase',  # 데이터베이스명
}

# 처리할 시트 및 테이블 매핑 (외래키 의존성 순서)
SHEET_CONFIGS = [
    # 1. 부모 테이블 먼저
    {
        'sheet_name': 'Vendors',
        'table': 'vendors',
        'required_columns': ['Vendor_ID', 'Vendor_Code', 'Vendor_Name'],
    },
    # 2. Vendors를 참조하는 테이블들
    {
        'sheet_name': 'Purchase Orders',
        'table': 'purchase_orders',
        'required_columns': ['PO_ID', 'PO_Number', 'PO_Date', 'Vendor_ID', 'Total_Amount'],
    },
    {
        'sheet_name': 'PO Lines',
        'table': 'po_lines',
        'required_columns': ['PO_Line_ID', 'PO_ID', 'Item_ID', 'Quantity'],
    },
    {
        'sheet_name': 'Invoices',
        'table': 'invoices',
        'required_columns': ['Invoice_ID', 'Invoice_Number', 'PO_ID', 'Vendor_ID'],
    },
    {
        'sheet_name': 'Goods Receipts',
        'table': 'goods_receipts',
        'required_columns': ['GR_ID', 'GR_Number', 'PO_ID', 'Vendor_ID'],
    },
]


def main():
    """메인 ETL 실행 함수"""

    # 엑셀 파일 경로 설정 (프로젝트 루트 기준)
    BASE_DIR = Path(__file__).parent.parent.parent
    data_path = BASE_DIR / 'data' / 'raw' / 'source_data' / 'ERP_Purchasing_Analytics.xlsx'

    # 데이터 파일 존재 여부 확인
    if not data_path.exists():
        print(f"❌ Error: Data file not found at {data_path}")
        print(f"   Please ensure the file exists at the specified location")
        return False

    print(f"✓ Data file found: {data_path}")
    print(f"✓ Database config: {DB_CONFIG['user']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}")
    print()

    # MySQL 클라이언트 초기화
    try:
        print("🔌 Connecting to MySQL database...")
        initialize_client(
            host=DB_CONFIG['host'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database'],
        )
        print("✓ Database connection successful")
        print()
    except Exception as e:
        print(f"❌ Failed to connect to database: {str(e)}")
        print(f"   Please check your database configuration:")
        print(f"   - Host: {DB_CONFIG['host']}")
        print(f"   - User: {DB_CONFIG['user']}")
        print(f"   - Database: {DB_CONFIG['database']}")
        return False

    # 필요한 테이블 자동 생성
    try:
        print("📊 Creating tables...")
        create_tables()
        print("✓ All tables created successfully")
        print()
    except Exception as e:
        print(f"❌ Failed to create tables: {str(e)}")
        return False

    # 각 시트를 순차적으로 처리
    results = {}
    success_count = 0
    failure_count = 0

    for config in SHEET_CONFIGS:
        print(f"\n{'=' * 60}")
        print(f"Processing: {config['sheet_name']} → {config['table']}")
        print(f"{'=' * 60}")

        try:
            result = run_csv_pipeline(
                path=data_path,
                sheet_name=config['sheet_name'],
                table=config['table'],
                required_columns=config['required_columns'],
            )

            results[config['table']] = result
            success_count += 1
            print()

        except Exception as e:
            print(f"❌ Pipeline failed: {str(e)}")
            failure_count += 1
            results[config['table']] = {'error': str(e)}
            print()

    # 결과 요약 출력
    print(f"\n{'=' * 60}")
    print(f"PIPELINE SUMMARY")
    print(f"{'=' * 60}")
    print(f"✓ Success: {success_count}/{len(SHEET_CONFIGS)}")
    print(f"❌ Failure: {failure_count}/{len(SHEET_CONFIGS)}")
    print()

    # 상세 결과
    for table, result in results.items():
        if result is None:
            print(f"⚠ {table}")
            print(f"   Validation: FAIL (No result)")
        elif isinstance(result, dict) and 'error' in result:
            print(f"❌ {table}")
            print(f"   Error: {result['error']}")
        else:
            validation = result.get('validation', {}) if result else {}
            load = result.get('load', {}) if result else {}
            print(f"✓ {table}")
            print(f"   Validation: {'PASS' if validation.get('is_valid') else 'FAIL'}")
            if load:
                print(f"   Inserted: {load.get('inserted_count', 0)}, Updated: {load.get('updated_count', 0)}")

    # 데이터베이스 연결 종료
    try:
        if _client and _client._connection:
            _client._connection.close()
        print("\n✓ Database connection closed")
    except Exception as e:
        print(f"⚠ Warning: {str(e)}")

    return failure_count == 0


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)