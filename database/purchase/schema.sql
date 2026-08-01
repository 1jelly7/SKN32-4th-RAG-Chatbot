-- ============================================================
-- purchase DB 스키마
-- ------------------------------------------------------------
-- ERP_Purchasing_Data_Cleaned.xlsx 의 10개 시트를 그대로 테이블로 옮긴 것입니다.
-- (Index 시트는 설명용이라 테이블로 만들지 않았습니다)
--
-- 실행 방법:
--   mysql -u JangGGo -p1234 -h 127.0.0.1 purchase < database/purchase/schema.sql
-- ============================================================

CREATE DATABASE IF NOT EXISTS purchase CHARACTER SET utf8mb4;
USE purchase;

-- ------------------------------------------------------------
-- Vendors (공급업체 마스터) - 다른 테이블이 참조하므로 가장 먼저 생성
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vendors (
    vendor_id           BIGINT PRIMARY KEY,
    company_id          BIGINT NOT NULL,
    vendor_code         VARCHAR(20) NOT NULL UNIQUE,
    vendor_name         VARCHAR(200) NOT NULL,
    vendor_type         VARCHAR(50),
    contact_person       VARCHAR(100),
    email               VARCHAR(200),
    phone_number         VARCHAR(50),
    address             VARCHAR(300),
    country             VARCHAR(100),
    tax_id               VARCHAR(50),
    payment_terms        VARCHAR(20),
    currency            VARCHAR(10),
    bank_account         VARCHAR(50),
    iban                VARCHAR(50),
    credit_limit         DECIMAL(14, 2),
    is_active            BOOLEAN DEFAULT TRUE,
    created_at           DATETIME,
    updated_at           DATETIME,
    created_by_user_id     BIGINT
);

-- ------------------------------------------------------------
-- Purchase Requisitions (구매 요청) - Purchase Orders가 참조
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS purchase_requisitions (
    purchase_requisition_id  BIGINT PRIMARY KEY,
    company_id              BIGINT NOT NULL,
    vendor_id                BIGINT,
    requester_id              BIGINT,
    department_id             BIGINT,
    requisition_number        VARCHAR(30) NOT NULL UNIQUE,
    requisition_date          DATE,
    required_by_date           DATE,
    item_description          VARCHAR(500),
    estimated_amount           DECIMAL(14, 2),
    currency                 VARCHAR(10),
    priority                 VARCHAR(20),
    justification             VARCHAR(500),
    approved_by_user_id         BIGINT,
    status                   VARCHAR(30),
    created_at                DATETIME,
    updated_at                DATETIME,
    created_by_user_id          BIGINT,
    FOREIGN KEY (vendor_id) REFERENCES vendors(vendor_id)
);

CREATE TABLE IF NOT EXISTS purchase_requisition_lines (
    purchase_requisition_line_id  BIGINT PRIMARY KEY,
    company_id                   BIGINT NOT NULL,
    purchase_requisition_id        BIGINT NOT NULL,
    line_number                   INT,
    item_id                       BIGINT,
    description                   VARCHAR(300),
    uom_id                         BIGINT,
    quantity                      DECIMAL(14, 2),
    unit_price                     DECIMAL(14, 4),
    discount_percent                DECIMAL(5, 2),
    tax_code_id                    BIGINT,
    tax_amount                     DECIMAL(14, 2),
    line_total                     DECIMAL(14, 2),
    created_at                    DATETIME,
    updated_at                    DATETIME,
    created_by_user_id               BIGINT,
    FOREIGN KEY (purchase_requisition_id) REFERENCES purchase_requisitions(purchase_requisition_id)
);

-- ------------------------------------------------------------
-- Purchase Orders (구매 주문)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS purchase_orders (
    purchase_order_id      BIGINT PRIMARY KEY,
    company_id             BIGINT NOT NULL,
    vendor_id               BIGINT,
    requisition_id           BIGINT,
    po_number              VARCHAR(30) NOT NULL UNIQUE,
    po_date                DATE,
    delivery_date            DATE,
    delivery_address          VARCHAR(300),
    subtotal               DECIMAL(14, 2),
    tax_amount              DECIMAL(14, 2),
    total_amount             DECIMAL(14, 2),
    currency               VARCHAR(10),
    payment_terms            VARCHAR(20),
    notes                  VARCHAR(500),
    approved_by_user_id        BIGINT,
    status                  VARCHAR(30),
    approval_request_id        BIGINT,
    created_at              DATETIME,
    updated_at              DATETIME,
    created_by_user_id         BIGINT,
    FOREIGN KEY (vendor_id) REFERENCES vendors(vendor_id),
    FOREIGN KEY (requisition_id) REFERENCES purchase_requisitions(purchase_requisition_id)
);

CREATE TABLE IF NOT EXISTS purchase_order_lines (
    purchase_order_line_id  BIGINT PRIMARY KEY,
    company_id              BIGINT NOT NULL,
    purchase_order_id         BIGINT NOT NULL,
    line_number              INT,
    item_id                  BIGINT,
    description              VARCHAR(300),
    uom_id                    BIGINT,
    quantity                 DECIMAL(14, 2),
    unit_price                DECIMAL(14, 4),
    discount_percent           DECIMAL(5, 2),
    tax_code_id               BIGINT,
    tax_amount                DECIMAL(14, 2),
    line_total                DECIMAL(14, 2),
    quantity_received           DECIMAL(14, 2),
    expected_date              DATE,
    created_at                DATETIME,
    updated_at                DATETIME,
    created_by_user_id           BIGINT,
    FOREIGN KEY (purchase_order_id) REFERENCES purchase_orders(purchase_order_id)
);

-- ------------------------------------------------------------
-- Goods Receipts (입고)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS goods_receipts (
    goods_receipt_id     BIGINT PRIMARY KEY,
    company_id            BIGINT NOT NULL,
    po_id                 BIGINT,
    vendor_id              BIGINT,
    gr_number             VARCHAR(30) NOT NULL UNIQUE,
    receipt_date           DATE,
    warehouse_id            BIGINT,
    received_by_user_id       BIGINT,
    notes                 VARCHAR(500),
    created_at             DATETIME,
    updated_at             DATETIME,
    created_by_user_id        BIGINT,
    FOREIGN KEY (po_id) REFERENCES purchase_orders(purchase_order_id),
    FOREIGN KEY (vendor_id) REFERENCES vendors(vendor_id)
);

CREATE TABLE IF NOT EXISTS goods_receipt_lines (
    goods_receipt_line_id  BIGINT PRIMARY KEY,
    company_id              BIGINT NOT NULL,
    goods_receipt_id          BIGINT NOT NULL,
    purchase_order_line_id      BIGINT,
    line_number              INT,
    item_id                  BIGINT,
    description              VARCHAR(300),
    uom_id                    BIGINT,
    quantity                 DECIMAL(14, 2),
    unit_price                DECIMAL(14, 4),
    discount_percent           DECIMAL(5, 2),
    tax_code_id               BIGINT,
    tax_amount                DECIMAL(14, 2),
    line_total                DECIMAL(14, 2),
    quantity_ordered            DECIMAL(14, 2),
    quantity_accepted           DECIMAL(14, 2),
    quantity_rejected           DECIMAL(14, 2),
    lot_number_id              BIGINT,
    created_at                DATETIME,
    updated_at                DATETIME,
    created_by_user_id           BIGINT,
    FOREIGN KEY (goods_receipt_id) REFERENCES goods_receipts(goods_receipt_id),
    FOREIGN KEY (purchase_order_line_id) REFERENCES purchase_order_lines(purchase_order_line_id)
);

-- ------------------------------------------------------------
-- Vendor Invoices (매입 세금계산서/청구서)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vendor_invoices (
    vendor_invoice_id     BIGINT PRIMARY KEY,
    company_id             BIGINT NOT NULL,
    vendor_id               BIGINT,
    po_id                  BIGINT,
    invoice_number           VARCHAR(30) NOT NULL UNIQUE,
    invoice_date             DATE,
    due_date                DATE,
    subtotal                DECIMAL(14, 2),
    tax_amount               DECIMAL(14, 2),
    total_amount              DECIMAL(14, 2),
    amount_paid              DECIMAL(14, 2),
    outstanding_amount          DECIMAL(14, 2),
    currency                VARCHAR(10),
    status                  VARCHAR(30),
    created_at               DATETIME,
    updated_at               DATETIME,
    created_by_user_id          BIGINT,
    FOREIGN KEY (vendor_id) REFERENCES vendors(vendor_id),
    FOREIGN KEY (po_id) REFERENCES purchase_orders(purchase_order_id)
);

CREATE TABLE IF NOT EXISTS vendor_invoice_lines (
    vendor_invoice_line_id  BIGINT PRIMARY KEY,
    company_id               BIGINT NOT NULL,
    vendor_invoice_id          BIGINT NOT NULL,
    line_number               INT,
    item_id                   BIGINT,
    description               VARCHAR(300),
    uom_id                     BIGINT,
    quantity                  DECIMAL(14, 2),
    unit_price                 DECIMAL(14, 4),
    discount_percent            DECIMAL(5, 2),
    tax_code_id                BIGINT,
    tax_amount                 DECIMAL(14, 2),
    line_total                 DECIMAL(14, 2),
    created_at                 DATETIME,
    updated_at                 DATETIME,
    created_by_user_id            BIGINT,
    FOREIGN KEY (vendor_invoice_id) REFERENCES vendor_invoices(vendor_invoice_id)
);

-- ------------------------------------------------------------
-- Procurement Reports (조달 리포트 - 요약/집계 성격)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS procurement_reports (
    procurement_report_id   BIGINT PRIMARY KEY,
    company_id               BIGINT NOT NULL,
    purchase_order_id          BIGINT,
    vendor_id                 BIGINT,
    item_id                   BIGINT,
    report_code               VARCHAR(30) NOT NULL UNIQUE,
    report_name               VARCHAR(200),
    report_type                VARCHAR(50),
    period_start                DATE,
    period_end                 DATE,
    total_spend                DECIMAL(14, 2),
    po_count                  INT,
    generated_by_user_id          BIGINT,
    generated_at                DATETIME,
    report_url                 VARCHAR(300),
    created_at                 DATETIME,
    updated_at                 DATETIME,
    created_by_user_id            BIGINT,
    FOREIGN KEY (purchase_order_id) REFERENCES purchase_orders(purchase_order_id),
    FOREIGN KEY (vendor_id) REFERENCES vendors(vendor_id)
);

-- 자주 쓰일 조회 패턴(공급업체별/기간별/상태별)에 인덱스를 추가합니다.
CREATE INDEX idx_po_vendor_date ON purchase_orders (vendor_id, po_date);
CREATE INDEX idx_po_status ON purchase_orders (status);
CREATE INDEX idx_invoice_status ON vendor_invoices (status);
CREATE INDEX idx_gr_receipt_date ON goods_receipts (receipt_date);
