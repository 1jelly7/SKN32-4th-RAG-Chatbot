"""
ETL 설정 파일
데이터베이스 연결 정보 및 파이프라인 구성을 관리합니다.
"""

from pathlib import Path

# ========== 데이터베이스 설정 ==========
DB_CONFIG = {
    'host': 'localhost',           # MySQL 서버 호스트
    'user': 'purchase',             # MySQL 사용자명
    'password': '1234',                # MySQL 비밀번호 (여기에 입력하세요)
    'database': 'purchase',        # 데이터베이스명
}

# ========== 데이터 경로 설정 ==========
DATA_RAW_DIR = Path('data/raw')              # 원본 데이터 디렉토리
DATA_PROCESSED_DIR = Path('data/processed')  # 처리된 데이터 디렉토리
LOGS_DIR = Path('logs')                      # 로그 디렉토리

# 데이터 소스
EXCEL_FILE = DATA_RAW_DIR / 'ERP_Purchasing_Analytics.xlsx'

# ========== ETL 파이프라인 설정 ==========
# 각 시트별 처리 설정
SHEET_CONFIGS = [
    {
        'sheet_name': 'Purchase Orders',
        'table': 'purchase_orders',
        'required_columns': ['PO_ID', 'PO_Number', 'PO_Date', 'Vendor_ID', 'Total_Amount'],
        'column_mapping': None,
        'type_mapping': {
            'PO_ID': 'int64',
            'Vendor_ID': 'int64',
            'Subtotal': 'float64',
            'Tax_Amount': 'float64',
            'Total_Amount': 'float64',
        },
    },
    {
        'sheet_name': 'PO Lines',
        'table': 'po_lines',
        'required_columns': ['PO_Line_ID', 'PO_ID', 'Item_ID', 'Quantity'],
        'column_mapping': None,
        'type_mapping': {
            'PO_Line_ID': 'int64',
            'PO_ID': 'int64',
            'Item_ID': 'int64',
            'Quantity': 'int64',
            'Unit_Price': 'float64',
            'Discount_Percent': 'float64',
            'Line_Total': 'float64',
        },
    },
    {
        'sheet_name': 'Vendors',
        'table': 'vendors',
        'required_columns': ['Vendor_ID', 'Vendor_Code', 'Vendor_Name'],
        'column_mapping': None,
        'type_mapping': {
            'Vendor_ID': 'int64',
        },
    },
    {
        'sheet_name': 'Invoices',
        'table': 'invoices',
        'required_columns': ['Invoice_ID', 'Invoice_Number', 'PO_ID', 'Vendor_ID'],
        'column_mapping': None,
        'type_mapping': {
            'Invoice_ID': 'int64',
            'PO_ID': 'int64',
            'Vendor_ID': 'int64',
            'Subtotal': 'float64',
            'Tax_Amount': 'float64',
            'Total_Amount': 'float64',
            'Amount_Paid': 'float64',
            'Outstanding_Amount': 'float64',
        },
    },
    {
        'sheet_name': 'Goods Receipts',
        'table': 'goods_receipts',
        'required_columns': ['GR_ID', 'GR_Number', 'PO_ID', 'Vendor_ID'],
        'column_mapping': None,
        'type_mapping': {
            'GR_ID': 'int64',
            'PO_ID': 'int64',
            'Vendor_ID': 'int64',
        },
    },
]

# ========== 디렉토리 생성 ==========
def ensure_directories():
    """필요한 디렉토리가 존재하는지 확인하고 생성합니다."""
    for directory in [DATA_RAW_DIR, DATA_PROCESSED_DIR, LOGS_DIR]:
        directory.mkdir(parents=True, exist_ok=True)
