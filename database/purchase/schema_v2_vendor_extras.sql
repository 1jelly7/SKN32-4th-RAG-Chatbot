-- ============================================================
-- purchase DB 추가 스키마 (ERP_Seed_Data_Sales_Purchasing.xlsx 반영)
-- ------------------------------------------------------------
-- 기존 database/purchase/schema.sql 에 없던 3개 테이블을 추가합니다.
-- 실행 순서: schema.sql을 먼저 실행한 뒤 이 파일을 실행하세요.
--
--   mysql -u JangGGo -p1234 -h 127.0.0.1 purchase < database/purchase/schema.sql
--   mysql -u JangGGo -p1234 -h 127.0.0.1 purchase < database/purchase/schema_v2_vendor_extras.sql
-- ============================================================

USE purchase;

CREATE TABLE IF NOT EXISTS vendor_contracts (
    vendor_contract_id  BIGINT PRIMARY KEY,
    vendor_id           BIGINT,
    contract_number       VARCHAR(30) NOT NULL UNIQUE,
    contract_name        VARCHAR(200),
    contract_type        VARCHAR(50),
    start_date          DATE,
    end_date           DATE,
    total_value         DECIMAL(14, 2),
    currency           VARCHAR(10),
    payment_terms        VARCHAR(50),
    auto_renew          BOOLEAN,
    document_url         VARCHAR(300),
    status             VARCHAR(30),
    FOREIGN KEY (vendor_id) REFERENCES vendors(vendor_id)
);

CREATE TABLE IF NOT EXISTS vendor_ratings (
    vendor_rating_id     BIGINT PRIMARY KEY,
    company_id           BIGINT NOT NULL,
    vendor_id            BIGINT,
    rating_period          VARCHAR(100),
    quality_score          DECIMAL(5, 2),
    delivery_score         DECIMAL(5, 2),
    pricing_score          DECIMAL(5, 2),
    service_score          DECIMAL(5, 2),
    overall_score          DECIMAL(5, 2),
    comments             VARCHAR(500),
    reviewed_by_user_id       BIGINT,
    review_date           DATE,
    created_at            DATETIME,
    updated_at            DATETIME,
    created_by_user_id        BIGINT,
    FOREIGN KEY (vendor_id) REFERENCES vendors(vendor_id)
);

-- 3-way 매칭(청구서-발주서-입고) 결과입니다. 기존 vendor_invoices/purchase_orders/
-- goods_receipts 테이블을 참조합니다.
CREATE TABLE IF NOT EXISTS invoice_matching (
    invoice_match_id      BIGINT PRIMARY KEY,
    company_id            BIGINT NOT NULL,
    vendor_invoice_id        BIGINT,
    po_id               BIGINT,
    gr_id               BIGINT,
    match_type            VARCHAR(20),
    invoice_amount          DECIMAL(14, 2),
    po_amount             DECIMAL(14, 2),
    gr_amount             DECIMAL(14, 2),
    variance_amount         DECIMAL(14, 2),
    match_status           VARCHAR(30),
    processed_by_user_id       BIGINT,
    processed_at           DATETIME,
    created_at            DATETIME,
    updated_at            DATETIME,
    created_by_user_id        BIGINT,
    FOREIGN KEY (vendor_invoice_id) REFERENCES vendor_invoices(vendor_invoice_id),
    FOREIGN KEY (po_id) REFERENCES purchase_orders(purchase_order_id),
    FOREIGN KEY (gr_id) REFERENCES goods_receipts(goods_receipt_id)
);
